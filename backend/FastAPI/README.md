FastAPI for booking trades
- Uses redis and Postgres for database retrieval

Current Features:
- Register
- Login
- Logout
- New Account
- Pair User to existing Account
- Get all of a user's accounts 
- Get User positions
- - All positions
- - All positions for 1 account
- - All positions for a specific ticker
- - Position for specific account and specific ticker
- Book a trade
- Get Trade data
- - All trade data
- - All trade data for account
- - All trade data for ticker
- - Trade data for specific account and specific ticker
- - All of above for a specific time range
- - One specific trade data

All of these also verify your cookie and write to redis and read from postgres as appopriate

The api is dependent on a postgres being up and running to even run in the first place. Additionally redis must be up to not get an error from every endpoint
- Recommended to use a docker compose to run the api. See the one in this folder as an example of what it should look like 