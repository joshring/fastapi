import requests
import time
import psycopg

from database.db_setup import db_conn_str

## These tests are designed to run against a running API and database, which you can start via
# docker compose up --build


def db_cleanup():
    """
    Give a clean events table for each test run

    Note:   Run this at the start of the test,
            then we can debug the DB contents in case of failure
    """
    with psycopg.connect(db_conn_str) as conn:
        conn.execute("delete from events")


def test_user_not_found():

    db_cleanup()

    time_now = int(time.time())

    resp = requests.post(
        url="http://localhost:8000/event",
        data=f"""
        {{
            "amount": "200.10",
            "type": "withdraw",
            "user_id": 66666666666,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 404


def test_time_invalid():

    db_cleanup()

    resp = requests.post(
        url="http://localhost:8000/event",
        data="""
        {
            "amount": "200.10",
            "type": "withdraw",
            "user_id": 66666666666,
            "t": -5000
        }
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    expected_body = {
        "detail": [
            {
                "type": "greater_than",
                "loc": ["body", "t"],
                "msg": "Input should be greater than 0",
                "input": -5000,
                "ctx": {"gt": 0},
            }
        ]
    }

    assert resp.json() == expected_body


def test_amount_invalid():

    db_cleanup()

    time_now = int(time.time())

    resp = requests.post(
        url="http://localhost:8000/event",
        data=f"""
        {{
            "amount": "200.0",
            "type": "withdraw",
            "user_id": 1,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    assert resp.json() == {"detail": "amount should be to two decimal places"}


def test_amount_negative():

    db_cleanup()

    time_now = int(time.time())

    resp = requests.post(
        url="http://localhost:8000/event",
        data=f"""
        {{
            "amount": "-200.00",
            "type": "withdraw",
            "user_id": 1,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    assert resp.json() == {"detail": "amount cannot be negative"}


def test_type_invalid():

    db_cleanup()

    time_now = int(time.time())

    resp = requests.post(
        url="http://localhost:8000/event",
        data=f"""
        {{
            "amount": "200.00",
            "type": "INVALID TYPE",
            "user_id": 1,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400

    assert resp.json() == {
        "detail": [
            {
                "ctx": {
                    "expected": "'deposit' or 'withdraw'",
                },
                "input": "INVALID TYPE",
                "loc": [
                    "body",
                    "type",
                ],
                "msg": "Input should be 'deposit' or 'withdraw'",
                "type": "enum",
            },
        ]
    }


def test_withdraw_gt_200():

    db_cleanup()

    time_now = int(time.time())

    resp = requests.post(
        url="http://localhost:8000/event",
        data=f"""
        {{
            "amount": "200.10",
            "type": "withdraw",
            "user_id": 1,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    resp_body = resp.json()
    assert resp_body == {"alert": True, "alert_codes": [1100], "user_id": 1}


def test_sum_depo_gt_200_in_30s_window():

    db_cleanup()

    time_now = int(time.time())

    for index in range(3):

        resp = requests.post(
            url="http://localhost:8000/event",
            data=f"""
            {{
                "amount": "70.00",
                "type": "deposit",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"},
        )
        print(resp.content)
        assert resp.status_code == 200

        resp_body = resp.json()

        if index == 2:
            assert resp_body == {"alert": True, "alert_codes": [123], "user_id": 1}

        if index < 2:
            assert resp_body == {"alert": False, "alert_codes": [], "user_id": 1}


def test_3_conseq_withdraws():

    db_cleanup()

    time_now = int(time.time())

    for index in range(3):

        resp = requests.post(
            url="http://localhost:8000/event",
            data=f"""
            {{
                "amount": "20.01",
                "type": "withdraw",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"},
        )
        print(resp.content)
        assert resp.status_code == 200

        resp_body = resp.json()

        if index == 2:
            assert resp_body == {"alert": True, "alert_codes": [30], "user_id": 1}

        if index < 2:
            assert resp_body == {"alert": False, "alert_codes": [], "user_id": 1}


def test_3_conseq_depo_increasing():

    db_cleanup()

    time_now = int(time.time())

    for index in range(3):

        amount = f"2{index}.00"

        resp = requests.post(
            url="http://localhost:8000/event",
            data=f"""
            {{
                "amount": "{amount}",
                "type": "deposit",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"},
        )
        print(resp.content)
        assert resp.status_code == 200

        resp_body = resp.json()

        if index == 2:
            assert resp_body == {"alert": True, "alert_codes": [300], "user_id": 1}

        if index < 2:
            assert resp_body == {"alert": False, "alert_codes": [], "user_id": 1}
