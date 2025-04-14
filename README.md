# Implementing safety alerting for tracking unusual user activity

## Endpoint: `POST /event`

#### JSON Body 
```json
{
	"type": "deposit",
	"amount": "42.00",
	"user_id": 1,
	"t": 10
}
```
#### Example JSON response
```json
{
	"alert": true,
	"alert_codes": [30, 123],
	"user_id": 1
}
```

#### Note:
To capture the patterns of behaviour indicative of an issue, and avoid users who are only very occasional users. 
I have used a sliding window lenth of 1 week over which we monitor user behaviour for these events over. 
This would need to comply with the regulators and need to be discussed but seems like a good starting point.


## Using Docker Compose
#### Build And Run
```bash
docker compose up --build
```

#### Run Integration Tests
```bash
DB_PORT=5432 DB_HOST=localhost DB_USER=postgres DB_NAME=midnite pytest
```

#### Finished
```bash
docker compose down
```

-----------------------------------------------------

## Outside Docker Compose
#### Create Virtual Environment
```bash
python3 -m venv .venv
```

#### Activate Virtual Environment
```bash
source .venv/bin/activate
```

#### Install Dependencies (Tested On Python 3.13 On Ubuntu)
```bash
pip install -r requirements.txt
```

#### Start Up Postgres Database
```bash
docker compose up db -d
```

#### Running The API
```bash
DB_PORT=5432 DB_HOST=localhost DB_USER=postgres DB_NAME=midnite fastapi dev main.py
```

#### Running The Integration Tests
```bash
DB_PORT=5432 DB_HOST=localhost DB_USER=postgres DB_NAME=midnite pytest
```

#### Finished
- Exit the api
```bash
docker compose down
```
