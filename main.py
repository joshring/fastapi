from fastapi import FastAPI, Body, Depends, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from http import HTTPStatus
from pydantic import BaseModel, Field, AfterValidator, model_validator

from enum import Enum
from typing import Annotated
import time

from psycopg import Connection
from psycopg.rows import dict_row
from database.db_setup import lifespan, db_conn


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def fastapi_bad_requests(request: Request, exc: RequestValidationError):
    """
    Convert HTTP 422 errors to more standard HTTP bad request 400
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.errors()},
    )


class EventBodyType(str, Enum):
    deposit = "deposit"
    withdraw = "withdraw"


def post_event_amount_validation(input: str) -> str:

    input_segs = input.split(".")
    # Should have a decimal
    if len(input_segs) != 2:
        return HTTPException(
            detail="amount should have a decimal and have two decimal places",
            status_code=HTTPStatus.BAD_REQUEST,
        )

    # Decimal part should be 2 digits long
    if len(input_segs[1]) != 2:
        raise HTTPException(
            detail="amount should be to two decimal places",
            status_code=HTTPStatus.BAD_REQUEST,
        )

    input_float = float(input)

    if input_float < 0:
        raise HTTPException(detail="amount cannot be negative", status_code=HTTPStatus.BAD_REQUEST)

    return input


class EventBody(BaseModel):
    model_config = {"extra": "forbid"}  # disallow extra fields

    amount: Annotated[str, AfterValidator(post_event_amount_validation)]
    type: EventBodyType
    user_id: int = Field(gt=0, description="Represents a unique user")
    t: int = Field(
        gt=0,
        description="The second we receive the payload, this will always be increasing and unique",
    )


class EventRespAlertCodes(int, Enum):
    withdr_over_100 = 1100
    three_conseq_withdr = 30  # in a row
    three_conseq_depo_incr = 300  ## ignores withdraws
    sum_depo_gt_200_in_30s_window = 123


class EventResponse(BaseModel):
    alert: bool = Field(description="must only be set when alert_codes is populated")
    alert_codes: set[EventRespAlertCodes]
    user_id: int = Field(gt=0, description="Represents a unique user")

    @model_validator(mode="after")
    def internal_consistency_check(self) -> "EventResponse":

        if self.alert is True and len(self.alert_codes) == 0:
            raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "alert set in error, without error codes")

        if self.alert is False and len(self.alert_codes) > 0:
            raise HTTPException(HTTPStatus.INTERNAL_SERVER_ERROR, "alert not set in error, with error_codes")

        return self


@app.post("/event")
async def post_event(
    new_event: Annotated[EventBody, Body()],
    conn: Annotated[Connection, Depends(db_conn)],
) -> EventResponse:
    """
    unusual activity notification
    """

    response = {"alert": False, "alert_codes": set(), "user_id": new_event.user_id}

    if float(new_event.amount) > 100 and new_event.type is EventBodyType.withdraw:
        response["alert"] = True
        response["alert_codes"].add(EventRespAlertCodes.withdr_over_100)

    cur = conn.cursor(row_factory=dict_row)

    # limit the comparisons to within a week, since that captures the intended behaviour
    # counter example, an inactive user with a pattern across 4 years should not flag in these checks
    seconds_per_week = 60 * 60 * 24 * 7
    current_unix_time = time.time()
    time_1_week_ago = current_unix_time - seconds_per_week
    time_30s_ago = current_unix_time - 30

    async with conn.transaction():

        # Validate the user exists
        query = await cur.execute(
            """
            select
                users.id
            from users
            where
                users.id = %s
            """,
            [new_event.user_id],
        )

        query_result = await query.fetchone()
        if query_result is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, f"userid: {new_event.user_id} not found")

        # =================================================
        # Only if new_event == withdraw
        #
        # three_conseq_withdr ## current event and two previous in order are all withdraws
        if new_event.type is EventBodyType.withdraw:

            query = await cur.execute(
                """
                -- Get all the events for the past week for our user, ordered by time descending
                with calc as (
                    select
                        events.id as events_id,
                        events.event_type
                    from
                        events
                    where 
                        events.t >= %s
                        and events.user_id = %s
                    order by events.t desc
                ),
                -- Take the two most recent events
                two_most_recent as (
                    select
                        calc.events_id,
                        calc.event_type
                    from 
                        calc
                    limit 2	
                )
                -- count up the number of events which were a withdraw
                select
                    count(two_most_recent.events_id) = 2 as two_prev_events_withdraws
                from 
                    two_most_recent
                where 
                    two_most_recent.event_type = 'withdraw';
                """,
                [time_1_week_ago, new_event.user_id],
            )

            query_result = await query.fetchone()
            if query_result is not None:
                # The new_event.type is a withdraw and the two most recent historical ones are too, add alert_codes
                if query_result.get("two_prev_events_withdraws") == True:
                    response["alert"] = True
                    response["alert_codes"].add(EventRespAlertCodes.three_conseq_withdr)

        # =================================================
        # Only if the new_event.type == deposit
        #
        # sum_depo_gt_200_in_30s_window ## current event is a deposit and two previous depo within 30s
        # three_conseq_depo_incr ## ignores withdraws if current event deposit, all increasing

        if new_event.type is EventBodyType.deposit:

            query = await cur.execute(
                """
                -- Sum the event.amount for the past 30s for our user which are deposits
                select
                    sum(events.amount) as sum_historical_events
                from
                    events
                where 
                    events.t >= %s
                    and events.user_id = %s
                    and events.event_type = 'deposit';
                """,
                [time_30s_ago, new_event.user_id],
            )

            query_result = await query.fetchone()
            if query_result is not None:
                # The new_event.type is a deposit and the combined sum is >200 in a 30s window
                if query_result.get("sum_historical_events"):

                    if (float(query_result["sum_historical_events"]) + float(new_event.amount)) > 200.0:
                        response["alert"] = True
                        response["alert_codes"].add(EventRespAlertCodes.sum_depo_gt_200_in_30s_window)

            query = await cur.execute(
                """
                -- return the last 2 stored deposit events
                select
                    events.amount,
                    events.t
                from
                    events
                where 
                    events.t >= %s
                    and events.user_id = %s
                    and events.event_type = 'deposit'
                order by events.t desc
                limit 2;
                """,
                [time_1_week_ago, new_event.user_id],
            )

            query_result = await query.fetchall()
            if query_result is not None and len(query_result) == 2:

                # query result has most recent first, so start from 1 to go 0 then compare with new_event
                # The deposit is the third consequtive (recent) deposit and is increasing
                if query_result[1]["amount"] < query_result[0]["amount"] < float(new_event.amount):
                    response["alert"] = True
                    response["alert_codes"].add(EventRespAlertCodes.three_conseq_depo_incr)

        # =================================================
        # Record the new_event and any alert and alert_codes

        alert_codes_inner = ",".join([f"{item.value}" for item in response["alert_codes"]])
        alert_codes = f"[{alert_codes_inner}]"

        await cur.execute(
            """
            insert into events(user_id, t, amount, event_type, alert, alert_codes)
            values
                (%s, %s, %s, %s, %s, %s);
            """,
            [
                new_event.user_id,
                new_event.t,
                new_event.amount,
                new_event.type,
                response["alert"],
                alert_codes if response["alert"] else None,
            ],
        )

    return EventResponse(**response)
