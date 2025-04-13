import requests
import time
import psycopg
from database.db_setup import db_conn_str


def db_cleanup():
    """
    Give a clean events table for each test run
    
    Note:   Run this at the start of the test, 
            then we can debug the DB contents in case of failure
    """
    with psycopg.connect(db_conn_str) as conn:
        conn.execute("delete from events")
        

def test_withdraw_gt_200():
    
    db_cleanup()
    
    time_now = int(time.time())
        
    resp = requests.post(
        url='http://localhost:8000/event',
        data=f"""
        {{
            "amount": "200.10",
            "type": "withdraw",
            "user_id": 1,
            "t": {time_now}
        }}
        """,
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 200

    resp_body = resp.json()
    assert resp_body == {'alert': True, 'alert_codes': [1100], 'user_id': 1}

    

        
def test_sum_depo_gt_200_in_30s_window():
    
    db_cleanup()
    
    time_now = int(time.time())
    
    for index in range(3):
        
        resp = requests.post(
            url='http://localhost:8000/event',
            data=f"""
            {{
                "amount": "70.00",
                "type": "deposit",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"}
        )
        print(resp.content)
        assert resp.status_code == 200
    
        resp_body = resp.json()
        
        if index == 2:
            assert resp_body == {'alert': True, 'alert_codes': [123], 'user_id': 1}
        
        if index < 2:
            assert resp_body == {'alert': False, 'alert_codes': [], 'user_id': 1}
    
    

        
def test_3_conseq_withdraws():
    
    db_cleanup()
    
    time_now = int(time.time())
    
    for index in range(3):
        
        resp = requests.post(
            url='http://localhost:8000/event',
            data=f"""
            {{
                "amount": "20.01",
                "type": "withdraw",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"}
        )
        print(resp.content)
        assert resp.status_code == 200
    
        resp_body = resp.json()
        
        if index == 2:
            assert resp_body == {'alert': True, 'alert_codes': [30], 'user_id': 1}
        
        if index < 2:
            assert resp_body == {'alert': False, 'alert_codes': [], 'user_id': 1}
    


        
def test_3_conseq_depo_increasing():
    
    db_cleanup()
    
    time_now = int(time.time())
    
    for index in range(3):
        
        amount = f"2{index}.00"
        
        resp = requests.post(
            url='http://localhost:8000/event',
            data=f"""
            {{
                "amount": "{amount}",
                "type": "deposit",
                "user_id": 1,
                "t": {time_now + index}
            }}
            """,
            headers={"Content-Type": "application/json"}
        )
        print(resp.content)
        assert resp.status_code == 200
    
        resp_body = resp.json()
        
        if index == 2:
            assert resp_body == {'alert': True, 'alert_codes': [300], 'user_id': 1}
        
        if index < 2:
            assert resp_body == {'alert': False, 'alert_codes': [], 'user_id': 1}
            
    
