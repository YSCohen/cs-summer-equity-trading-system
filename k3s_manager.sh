#!/usr/bin/env bash
# k3s_manager.sh - Interactive utility to manage K3s nodes over Tailscale and FluxCD

# Function to check if K3s is installed
check_installation() {
    if command -v k3s &>/dev/null; then
        if systemctl is-active --quiet k3s; then
            echo -e "\e[32m[Installed - Control Plane (Active)]\e[0m"
        elif systemctl is-active --quiet k3s-agent; then
            echo -e "\e[32m[Installed - Worker Node (Active)]\e[0m"
        else
            echo -e "\e[33m[Installed - Inactive/Unknown State]\e[0m"
        fi
    else
        echo -e "\e[31m[Not Installed]\e[0m"
    fi
}

# Function to ensure Tailscale is up and return the IP
setup_tailscale() {
    if ! command -v tailscale &>/dev/null; then
        echo "📦 Installing Tailscale..."
        curl -fsSL https://tailscale.com/install.sh | sh
    fi

    sudo systemctl enable tailscaled >/dev/null 2>&1 || true

    if ! tailscale status &>/dev/null; then
        echo "⚠️ Tailscale is not connected. Please authenticate:"
        sudo tailscale up
    fi

    TAILSCALE_IP=$(tailscale ip -4)
    echo "✅ Tailscale IP detected: ${TAILSCALE_IP}"
}

# Function to configure rootless kubectl access
setup_rootless_kubectl() {
    echo "🔧 Configuring rootless kubectl access..."
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $(id -u):$(id -g) ~/.kube/config
    sed -i "s/127.0.0.1/${TAILSCALE_IP}/g" ~/.kube/config

    # Append to shell profiles if not already present
    grep -qxF 'export KUBECONFIG=~/.kube/config' ~/.bashrc 2>/dev/null || echo 'export KUBECONFIG=~/.kube/config' >>~/.bashrc
    grep -qxF 'export KUBECONFIG=~/.kube/config' ~/.zshrc 2>/dev/null || echo 'export KUBECONFIG=~/.kube/config' >>~/.zshrc

    # Export for the current script session
    export KUBECONFIG=~/.kube/config
    echo "✅ Kubectl is now accessible without sudo (Restart your terminal to apply globally)."
}

# Function to install/join a Control Plane
install_control_plane() {
    setup_tailscale

    read -p "Are you joining an EXISTING Control Plane? (y/N): " join_existing
    if [[ "$join_existing" =~ ^[Yy]$ ]]; then
        read -p "Enter the existing Control Plane Tailscale IP: " JOIN_IP
        read -p "Enter the K3S_TOKEN: " JOIN_TOKEN

        if [ -z "$JOIN_IP" ] || [ -z "$JOIN_TOKEN" ]; then
            echo "❌ ERROR: IP and Token are required to join."
            return
        fi

        echo "📦 Joining Existing HA Cluster as a Control Plane..."
        curl -sfL https://get.k3s.io | K3S_TOKEN="${JOIN_TOKEN}" INSTALL_K3S_EXEC="server \
          --server https://${JOIN_IP}:6443 \
          --node-ip=${TAILSCALE_IP} \
          --flannel-iface=tailscale0 \
          --bind-address=${TAILSCALE_IP} \
          --advertise-address=${TAILSCALE_IP} \
          --tls-san=${TAILSCALE_IP}" sh -s -
    else
        echo "📦 Initializing New HA K3s Server (embedded etcd)..."
        curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
          --cluster-init \
          --node-ip=${TAILSCALE_IP} \
          --flannel-iface=tailscale0 \
          --bind-address=${TAILSCALE_IP} \
          --advertise-address=${TAILSCALE_IP} \
          --tls-san=${TAILSCALE_IP}" sh -s -
    fi

    sudo systemctl enable k3s >/dev/null 2>&1 || true

    echo "⏳ Waiting for K3s API to become available..."
    until sudo k3s kubectl get nodes &>/dev/null; do sleep 2; done

    if ! command -v flux &>/dev/null; then curl -s https://fluxcd.io/install.sh | sudo bash; fi
    if ! command -v helm &>/dev/null; then curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash; fi

    setup_rootless_kubectl
    echo "🎉 Control Plane Bootstrap Complete!"
}

# Function to install a Worker Node
install_worker() {
    setup_tailscale

    read -p "Enter the Control Plane Tailscale IP: " CP_IP
    read -p "Enter the K3S_TOKEN: " WORKER_TOKEN

    if [ -z "$CP_IP" ] || [ -z "$WORKER_TOKEN" ]; then
        echo "❌ ERROR: Control Plane IP and Token are required."
        return
    fi

    echo "📦 Joining K3s Cluster as a Worker..."
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="agent \
      --node-ip=${TAILSCALE_IP} \
      --flannel-iface=tailscale0" \
        K3S_URL="https://${CP_IP}:6443" \
        K3S_TOKEN="${WORKER_TOKEN}" sh -s -

    sudo systemctl enable k3s-agent >/dev/null 2>&1 || true

    echo "🎉 Worker Node Bootstrap Complete!"
}

# Function to show the current token
show_token() {
    # Using sudo test ensures we can read the root-owned file
    if sudo test -f /var/lib/rancher/k3s/server/node-token; then
        echo "🔑 Current K3s Cluster Token:"
        sudo cat /var/lib/rancher/k3s/server/node-token
        echo ""
    else
        echo "❌ Token not found. This node might not be a Control Plane."
    fi
}

# Function to setup Local USB Storage purely via K3s auto-deploy
setup_local_storage() {
    echo "💽 Configuring Local USB Storage..."
    read -p "Enter the local mount path [/mnt/usb-storage]: " USB_PATH
    USB_PATH=${USB_PATH:-/mnt/usb-storage}

    echo "Generating Kubernetes manifest for local storage..."
    cat <<EOF | sudo tee /var/lib/rancher/k3s/server/manifests/usb-storage.yaml >/dev/null
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: usb-storage-pv
spec:
  capacity:
    storage: 500Gi
  volumeMode: Filesystem
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  hostPath:
    path: ${USB_PATH}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: usb-storage-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  resources:
    requests:
      storage: 500Gi
EOF
    echo "✅ Local storage manifest deployed directly to K3s! (Bypassing Flux)"
}

# Function to uninstall K3s
uninstall_k3s() {
    read -p "⚠️ Are you sure you want to uninstall K3s? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        if [ -x /usr/local/bin/k3s-uninstall.sh ]; then
            echo "🗑️ Uninstalling Control Plane..."
            /usr/local/bin/k3s-uninstall.sh
        elif [ -x /usr/local/bin/k3s-agent-uninstall.sh ]; then
            echo "🗑️ Uninstalling Worker Node..."
            /usr/local/bin/k3s-agent-uninstall.sh
        else
            echo "❌ No uninstall scripts found. Is K3s installed?"
        fi
    else
        echo "Aborted."
    fi
}

# Function to bootstrap FluxCD
bootstrap_flux() {
    if ! command -v flux &>/dev/null; then
        echo "❌ Flux CLI is not installed. Please install a Control Plane first."
        return
    fi

    echo ""
    echo "🚢 Bootstrapping FluxCD..."

    read -s -p "Enter your GITHUB_TOKEN: " GITHUB_TOKEN
    echo ""
    read -p "Enter GitHub Owner [SM26-Industrial-Software-Dev]: " GITHUB_OWNER
    GITHUB_OWNER=${GITHUB_OWNER:-SM26-Industrial-Software-Dev}
    read -p "Enter Repository Name [equity-trading-system]: " GITHUB_REPO
    GITHUB_REPO=${GITHUB_REPO:-equity-trading-system}
    read -p "Enter Branch [main]: " GITHUB_BRANCH
    GITHUB_BRANCH=${GITHUB_BRANCH:-main}
    read -p "Enter Path [./k8s/clusters/k3s]: " GITHUB_PATH
    GITHUB_PATH=${GITHUB_PATH:-./k8s/clusters/k3s}

    export GITHUB_TOKEN=$GITHUB_TOKEN

    flux bootstrap github \
        --owner="${GITHUB_OWNER}" \
        --repository="${GITHUB_REPO}" \
        --branch="${GITHUB_BRANCH}" \
        --path="${GITHUB_PATH}" \
        --personal=false \
        --token-auth

    unset GITHUB_TOKEN
    echo "✅ Flux bootstrap complete!"
}

setup_db_secrets() {
    echo "🔐 Generating db-credentials secret..."
    PG_PASS=$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-24)

    for NS in data backend; do
        echo "Applying secret to namespace: $NS"
        kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
        kubectl create secret generic db-credentials \
            --from-literal=POSTGRES_USER=trade_admin \
            --from-literal=POSTGRES_PASSWORD="$PG_PASS" \
            --namespace="$NS" \
            --dry-run=client -o yaml | kubectl apply -f -
    done
    echo "✅ db-credentials secret applied."
}

# Function to enable Tailscale Funnel
update_self() {
    echo "⬇️ Pulling latest k3s_manager.sh from upstream..."
    local REPO_URL="https://raw.githubusercontent.com/SM26-Industrial-Software-Dev/equity-trading-system/main/k3s_manager.sh"
    local TMP_FILE=$(mktemp)

    if curl -sSL "$REPO_URL" -o "$TMP_FILE"; then
        mv "$TMP_FILE" "$0"
        chmod +x "$0"
        echo "✅ Successfully updated. Please re-run the script."
        exit 0
    else
        echo "❌ Update failed. Network or repository issue."
        rm "$TMP_FILE"
        exit 1
    fi
}

# Main Menu Loop
while true; do
    echo ""
    echo "======================================"
    echo " 🚀 K3s Cluster Manager "
    echo " Status: $(check_installation)"
    echo "======================================"
    echo "1) Bootstrap/Join Control Plane"
    echo "2) Join as Worker Node"
    echo "3) Show Cluster Token"
    echo "4) Configure Local USB Storage"
    echo "5) Bootstrap FluxCD"
    echo "6) Uninstall K3s"
    echo "7) Setup Database Secrets"
    echo "8) Update Manager"
    echo "9) Exit"
    echo "======================================"
    read -p "Select an option [1-9]: " choice

    case $choice in
    1) install_control_plane ;;
    2) install_worker ;;
    3) show_token ;;
    4) setup_local_storage ;;
    5) bootstrap_flux ;;
    6) uninstall_k3s ;;
    7) setup_db_secrets ;;
    8) update_self ;;
    9)
        echo "Goodbye!"
        exit 0
        ;;
    *) echo "❌ Invalid option. Please try again." ;;
    esac
done
