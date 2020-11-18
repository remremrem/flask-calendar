import json
import os, sys
import time
from datetime import datetime
import datetime as dt
from typing import Dict, List, Optional, cast

import flask_calendar.constants as constants
from flask import current_app
from flask_calendar.gregorian_calendar import GregorianCalendar

KEY_TASKS = "tasks"
KEY_USERS = "users"
KEY_ACCOUNTS = "accounts"
KEY_BALANCE = "balance"
KEY_BALANCES = "balances"
KEY_NORMAL_TASK = "normal"
KEY_REPETITIVE_TASK = "repetition"


class CalendarData:

    REPETITION_TYPE_WEEKLY = "w"
    REPETITION_TYPE_MONTHLY = "m"
    REPETITION_SUBTYPE_WEEK_DAY = "w"
    REPETITION_SUBTYPE_MONTH_DAY = "m"

    def __init__(self, data_folder: str, first_weekday: int = constants.WEEK_START_DAY_MONDAY) -> None:
        self.data_folder = data_folder
        self.gregorian_calendar = GregorianCalendar
        self.gregorian_calendar.setfirstweekday(first_weekday)

    def load_calendar(self, filename: str) -> Dict:
        with open(os.path.join(".", self.data_folder, "{}.json".format(filename))) as file:
            contents = json.load(file)
        if type(contents) is not dict:
            raise ValueError("Error loading calendar from file '{}'".format(filename))
        return cast(Dict, contents)


    def users_list(self, data: Optional[Dict] = None, calendar_id: Optional[str] = None) -> List:
        if data is None:
            if calendar_id is None:
                raise ValueError("Need to provide either calendar_id or loaded data")
            else:
                data = self.load_calendar(calendar_id)
        if KEY_USERS not in data:
            raise ValueError("Incomplete data for calendar id '{}'".format(calendar_id))

        return cast(List, data[KEY_USERS])


    def user_details(self, username: str, data: Optional[Dict] = None, calendar_id: Optional[str] = None,) -> Dict:
        if data is None:
            if calendar_id is None:
                raise ValueError("Need to provide either calendar_id or loaded data")
            else:
                data = self.load_calendar(calendar_id)
        if KEY_USERS not in data:
            raise ValueError("Incomplete data for calendar id '{}'".format(calendar_id))

        return cast(Dict, data[KEY_USERS][username])


    @staticmethod
    def is_past(year: int, month: int, current_year: int, current_month: int) -> bool:
        if year < current_year:
            return True
        elif year == current_year:
            if month < current_month:
                return True
        return False
    
    
    def accounts_from_calendar(self, data: Dict) -> List:
        if not data:
            raise ValueError("Incomplete data for calendar")
        if KEY_ACCOUNTS not in data:
            return {}
        else:
            return data[KEY_ACCOUNTS]
    
    
    def balance_from_calendar(self, data: Dict) -> List:
        if not data:
            raise ValueError("Incomplete data for calendar")
        
        return data[KEY_BALANCE]


    def tasks_from_calendar(self, year: int, month: int, data: Dict) -> Dict:
        if not data or KEY_TASKS not in data:
            raise ValueError("Incomplete data for calendar")
        if not all(
            [
                KEY_NORMAL_TASK in data[KEY_TASKS],
                KEY_REPETITIVE_TASK in data[KEY_TASKS],
            ]
        ):
            raise ValueError("Incomplete data for calendar")

        tasks = {}  # type: Dict

        (current_day, current_month, current_year,) = self.gregorian_calendar.current_date()

        for day in self.gregorian_calendar.month_days(year, month):
            month_str = str(day.month)
            year_str = str(day.year)
            if (
                year_str in data[KEY_TASKS][KEY_NORMAL_TASK]
                and month_str in data[KEY_TASKS][KEY_NORMAL_TASK][year_str]
                and month_str not in tasks
            ):
                tasks[month_str] = data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str]

        return tasks


    def hide_past_tasks(self, year: int, month: int, tasks: Dict) -> None:
        (current_day, current_month, current_year,) = self.gregorian_calendar.current_date()

        for day in self.gregorian_calendar.month_days(year, month):
            month_str = str(day.month)

            # empty past months and be careful of future dates, which might not have tasks
            if self.is_past(day.year, day.month, current_year, current_month) or month_str not in tasks:
                tasks[month_str] = {}

            for task_day_number in tasks[month_str]:
                if day.month == current_month and int(task_day_number) < current_day:
                    tasks[month_str][task_day_number] = []


    def task_from_calendar(self, calendar_id: str, year: int, month: int, day: int, task_id: int) -> Dict:
        data = self.load_calendar(calendar_id)

        year_str = str(year)
        month_str = str(month)
        day_str = str(day)

        for index, task in enumerate(data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str]):
            if task["id"] == task_id:
                task["repeats"] = False
                task["date"] = self.date_for_frontend(year, month, day)
                return cast(Dict, task)
        raise ValueError("Task id '{}' not found".format(task_id))


    def repetitive_task_from_calendar(self, calendar_id: str, year: int, month: int, task_id: int) -> Dict:
        data = self.load_calendar(calendar_id)

        task = [task for task in data[KEY_TASKS][KEY_REPETITIVE_TASK] if task["id"] == task_id][0]  # type: Dict
        task["repeats"] = True
        task["date"] = self.date_for_frontend(year, month, 1)
        return task


    @staticmethod
    def date_for_frontend(year: int, month: int, day: int) -> str:
        return "{0}-{1:02d}-{2:02d}".format(int(year), int(month), int(day))

    def add_repetitive_tasks_from_calendar(self, year: int, month: int, data: Dict, tasks: Dict) -> Dict:
        (current_day, current_month, current_year,) = self.gregorian_calendar.current_date()

        repetitive_tasks = self._repetitive_tasks_from_calendar(year, month, data)

        for repetitive_tasks_month in repetitive_tasks:
            for day, day_tasks in repetitive_tasks[repetitive_tasks_month].items():
                if repetitive_tasks_month not in tasks:
                    tasks[repetitive_tasks_month] = {}
                if day not in tasks[repetitive_tasks_month]:
                    tasks[repetitive_tasks_month][day] = []

                for task in day_tasks:
                    tasks[repetitive_tasks_month][day].append(task)
        print("ADD REP TASKS OH YEAH DAWG!!!: ", tasks, file=sys.stderr)
        return tasks
    
    def delete_account(self, calendar_id: str, account_name: str) -> None:
        deleted = False
        data = self.load_calendar(calendar_id)
        if account_name in data[KEY_ACCOUNTS]:
                data[KEY_ACCOUNTS].pop(account_name)
        self._save_calendar(data, filename=calendar_id)
        

    def delete_task(self, calendar_id: str, year_str: str, month_str: str, day_str: str, task_id: int,) -> None:
        deleted = False
        data = self.load_calendar(calendar_id)

        if (
            year_str in data[KEY_TASKS][KEY_NORMAL_TASK]
            and month_str in data[KEY_TASKS][KEY_NORMAL_TASK][year_str]
            and day_str in data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str]
        ):
            for index, task in enumerate(data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str]):
                if task["id"] == task_id:
                    data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str].pop(index)
                    deleted = True

        if not deleted:
            for index, task in enumerate(data[KEY_TASKS][KEY_REPETITIVE_TASK]):
                if task["id"] == task_id:
                    data[KEY_TASKS][KEY_REPETITIVE_TASK].pop(index)

        self._save_calendar(data, filename=calendar_id)


    def update_task_day(
        self, calendar_id: str, year_str: str, month_str: str, day_str: str, task_id: int, new_day_str: str,
    ) -> None:
        data = self.load_calendar(calendar_id)

        task_to_update = None
        for index, task in enumerate(data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str]):
            if task["id"] == task_id:
                task_to_update = data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str].pop(index)

        if task_to_update is None:
            return

        if new_day_str not in data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str]:
            data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][new_day_str] = []
        data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][new_day_str].append(task_to_update)

        self._save_calendar(data, filename=calendar_id)


    def update_task_amount(
        self, calendar_id: str, year: str, month: str, day: str, task_id: int, new_amount: float, repeats: bool
    ) -> None:
        data = self.load_calendar(calendar_id)
        
        
        if repeats: #if its a repeating task keep the dated transaction amount in the account "transactions" dictionary
            account = None
            for t in data[KEY_TASKS][KEY_REPETITIVE_TASK]: #first find out the account name
                if int(t["id"]) == task_id:
                    account = t["account"]
                    break
            if account: #then update the account's transaction dictionary
                if not "transactions" in data[KEY_ACCOUNTS][account]:
                    data[KEY_ACCOUNTS][account]["transactions"] = {}
                # {{accounts: {account_name: {transactions: {12345_year-month-day: new_amount} } } } } }
                data[KEY_ACCOUNTS][account]["transactions"][ str(task_id) + "_" + "-".join([ str(year), str(month), str(day) ]) ] = str(round(float(new_amount), 2))
        else: # if it's not a repeating task, change the amount in the task itself
            updated = False
            for index, task in enumerate(data[KEY_TASKS][KEY_NORMAL_TASK][year][month][day]):
                if task["id"] == task_id:
                    print("[KEY_TASKS][KEY_NORMAL_TASK][year][month]: ", data[KEY_TASKS][KEY_NORMAL_TASK][year][month], "DAY: ", day, file=sys.stderr)
                    data[KEY_TASKS][KEY_NORMAL_TASK][year][month][day][index]["amount"] = new_amount
                    updated = True
                

            if not updated:
                return
            


        self._save_calendar(data, filename=calendar_id)
        

    def create_task(
        self,
        calendar_id: str,
        year: Optional[int],
        month: Optional[int],
        day: Optional[int],
        account: str,
        amount: str,
        credit_debit: str,
        details: str,
        color: str,
        has_repetition: bool,
        repetition_type: Optional[str],
        repetition_subtype: Optional[str],
        repetition_value: int,
    ) -> bool:
        details = details if len(details) > 0 else "&nbsp;"
        data = self.load_calendar(calendar_id)

        new_task = {
            "id": int(time.time()),
            "color": color,
            "amount": amount,
            "account": account,
            "credit_debit":credit_debit,
            "details": details,
        }
        if has_repetition:
            if repetition_type == self.REPETITION_SUBTYPE_MONTH_DAY and repetition_value == 0:
                return False
            new_task["repetition_type"] = repetition_type
            new_task["repetition_subtype"] = repetition_subtype
            new_task["repetition_value"] = repetition_value
            data[KEY_TASKS][KEY_REPETITIVE_TASK].append(new_task)
        else:
            if year is None or month is None or day is None:
                return False
            year_str = str(year)
            month_str = str(month)
            day_str = str(day)
            if year_str not in data[KEY_TASKS][KEY_NORMAL_TASK]:
                data[KEY_TASKS][KEY_NORMAL_TASK][year_str] = {}
            if month_str not in data[KEY_TASKS][KEY_NORMAL_TASK][year_str]:
                data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str] = {}
            if day_str not in data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str]:
                data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str] = []
            data[KEY_TASKS][KEY_NORMAL_TASK][year_str][month_str][day_str].append(new_task)

        self._save_calendar(data, filename=calendar_id)
        return True
    
    
    def create_account(
        self, calendar_id: str, account_name: str) -> None:
        print("CALENDAR DATA -> CREARE_ACCOUNT: ", account_name, file=sys.stderr)
        data = self.load_calendar(calendar_id)
        if "accounts" not in data:
            data[KEY_ACCOUNTS] = {}
        if account_name not in data[KEY_ACCOUNTS]:
            data[KEY_ACCOUNTS][account_name] = {}
        self._save_calendar(data, filename=calendar_id)
        return True
    
    
    def set_balance(
        self, calendar_id: str, new_balance: float) -> None:
        print("CALENDAR DATA -> SET_BALANCE: ", new_balance, file=sys.stderr)
        data = self.load_calendar(calendar_id)
        data[KEY_BALANCE] = new_balance
        self._save_calendar(data, filename=calendar_id)
        return True
    
    
    def _get_task_by_id(self, data: dict, task_id: str):
        print("CALENDAR DATA -> get_task_by_id: ", task_id, file=sys.stderr)

        index = 0
        for task in data[KEY_TASKS][KEY_REPETITIVE_TASK]:
            if task["id"] == task_id:
                date = [None, None, day]
                kind = "repeats"
                return [task, kind, date, index]
            index += 1
        
        for year in data[KEY_TASKS][KEY_NORMAL_TASK]:
            for month in data[KEY_TASKS][KEY_NORMAL_TASK][year]:
                for day in data[KEY_TASKS][KEY_NORMAL_TASK][year][month]:
                    index = 0
                    for task in data[KEY_TASKS][KEY_NORMAL_TASK][year][month][day]:
                        if task["id"] == task_id:
                            date = (int(year), int(month), int(day))
                            kind = "normal"
                            return [task, kind, date, index]
                        index += 1
    
    
    def _get_repetitive_task_amount_by_date(self, data: dict, task: dict, date: list): #date=(year, month, day)
        print("CALENDAR DATA -> _get_repetitive_task_amount_by_date: ", task, file=sys.stderr)
        amount = task["amount"]
        amounts = self._repititive_task_amounts(data, task)
        if date in amounts:
            amount = amounts[date]
        credit_debit = 1
        if task["credit_debit"] == "debit":
            credit_debit = -1
        amount =  '{0:.2f}'.format((abs(float(amount)) * credit_debit))
        return amount
                    
    
    def _repititive_task_amounts(self, data: dict, task: dict) -> dict:
        print("CALENDAR DATA -> _repetitive_task_amounts: ", task, file=sys.stderr)
        account = task["account"]
        amounts = {}
        if "transactions" in data[KEY_ACCOUNTS][account]:
            transactions = data[KEY_ACCOUNTS][account]["transactions"]
        else: return amounts
        for trans in transactions:
            
            amount = transactions[trans]
            tid = trans.split("_")[0]
            date = trans.split("_")[1].split("-") #["year", "month", "day"]
            date = tuple(list(map(int, date))) #(year, month, day)
            if str(tid) == str(task["id"]):
                amounts[date] = amount
        return amounts

    
    def sort_balances(self, calendar_id: str, max_months: int) -> None:
        print("CALENDAR DATA -> SORT_BALANCES: ", file=sys.stderr)
        data = self.load_calendar(calendar_id)
        
        balance_keys = []
        balance_values = []
        
        today = self.gregorian_calendar.current_date() #[day, month, year]
        c = max_months
        tasks = []
        while c > -1:
            month = today[1]+c
            year = today[2]
            if month > 12:
                month -= 12
                year += 1
            tasks.append([year, month, self._repetitive_tasks_from_calendar(year, month, data)[str(month)]])
            c-=1
        
        trans = {}
        for month in tasks:
            for day in month[2]:
                d = (int(month[0]), int(month[1]), int(day))
                trans[d] = []
                print(year, month, "DAYDAYDAY: ", day, file=sys.stderr)
                for task in month[2][day]:
                    amount = self._get_repetitive_task_amount_by_date(data, task, d)
                    trans[d].append(amount)
        print("REPETITIVE TASK AMOUNT LIST BY DATES AND VALUES: ", trans, file=sys.stderr)
        
        tasks = data[KEY_TASKS][KEY_NORMAL_TASK]
        print("TAAAAAAAASKS: ", tasks, file=sys.stderr)
        c = max_months 
        while c > -1:
            month = today[1]+c
            year = today[2]
            if month > 12:
                month -= 12
                year += 1  
            if str(year) in tasks:
                print("y: ", year, file=sys.stderr) 
                if str(month) in tasks[str(year)]:
                    print("m: ", month, file=sys.stderr)
                    for day in list(range(1,32)):
                        if str(day) in tasks[str(year)][str(month)]:
                            print("d: ", day, file=sys.stderr)
                            d = (int(year), int(month), int(day))
                            if d not in trans:
                                trans[d] = []
                            for task in tasks[str(year)][str(month)][str(day)]:
                                credit_debit = -1
                                if task["credit_debit"] == "credit":
                                    credit_debit = 1
                                trans[d].append('{0:.2f}'.format((abs(float(task["amount"])) * credit_debit)))
                            
            c -=1
        
        sorted_trans = list(sorted(trans))
        sorted_trans.reverse()
        
        current = float(data[KEY_BALANCE])
        balances = {}
        print("sorted_trans: ", sorted_trans, file=sys.stderr)
        print("today: ", today, file=sys.stderr)
        now = datetime.today().toordinal()
        while sorted_trans:
            t = sorted_trans.pop()
            tdate = dt.date(t[0], t[1], t[2]).toordinal()
            print("t: ", t, file=sys.stderr)
            if tdate > now:
                for each in trans[t]:
                    current +=  float(each)
                balances[t] = '{0:.2f}'.format(float(current))
        print("BALANCES: ", balances, file=sys.stderr)
        
        if KEY_BALANCES not in data:
            data[KEY_BALANCES] = {}
        for bal in balances:
            data[KEY_BALANCES][str(bal)] = balances[bal]

        self._save_calendar(data, filename=calendar_id)
        return True

    
    def get_balances(self, calendar_id: str) -> dict:
        print("CALENDAR DATA -> GET_BALANCES: ", file=sys.stderr)
        data = self.load_calendar(calendar_id)
        
        if KEY_BALANCES in data:
            return data[KEY_BALANCES]
        else: return {}


    @staticmethod
    def add_task_to_list(tasks: Dict, day_str: str, month_str: str, new_task: Dict) -> None:
        if day_str not in tasks[month_str]:
            tasks[month_str][day_str] = []
        tasks[month_str][day_str].append(new_task)

    def _repetitive_tasks_from_calendar(self, year: int, month: int, data: Dict) -> Dict:
        if KEY_TASKS not in data:
            ValueError("Incomplete data for calendar")
        if KEY_REPETITIVE_TASK not in data[KEY_TASKS]:
            ValueError("Incomplete data for calendar")

        repetitive_tasks = {}  # type: Dict
        year_and_months = set(
            [(source_day.year, source_day.month) for source_day in self.gregorian_calendar.month_days(year, month)]
        )

        for source_year, source_month in year_and_months:
            month_str = str(source_month)
            year_str = str(source_year)
            repetitive_tasks[month_str] = {}

            for task in data[KEY_TASKS][KEY_REPETITIVE_TASK]:
                id_str = str(task["id"])
                monthly_task_assigned = False
                for week in self.gregorian_calendar.month_days_with_weekday(source_year, source_month):
                    for weekday, day in enumerate(week):
                        if day == 0:
                            continue
                        day_str = str(day)
                        if (
                            task["repetition_type"] == self.REPETITION_TYPE_WEEKLY 
                            and task["repetition_value"] == weekday
                        ):
                            self.add_task_to_list(repetitive_tasks, day_str, month_str, task)
                        elif task["repetition_type"] == self.REPETITION_TYPE_MONTHLY:
                            if task["repetition_subtype"] == self.REPETITION_SUBTYPE_WEEK_DAY:
                                if task["repetition_value"] == weekday and not monthly_task_assigned:
                                    monthly_task_assigned = True
                                    self.add_task_to_list(repetitive_tasks, day_str, month_str, task)
                            else:
                                if task["repetition_value"] == day:
                                    self.add_task_to_list(repetitive_tasks, day_str, month_str, task)

        return repetitive_tasks
    

    def _save_calendar(self, data: Dict, filename: str) -> None:
        self._clear_empty_entries(data)
        with open(os.path.join(".", self.data_folder, "{}.json".format(filename)), "w+") as file:
            json.dump(data, file)


    @staticmethod
    def _clear_empty_entries(data: Dict) -> None:
        years_to_delete = []

        for year in data[KEY_TASKS][KEY_NORMAL_TASK]:
            months_to_delete = []
            for month in data[KEY_TASKS][KEY_NORMAL_TASK][year]:
                days_to_delete = []
                for day in data[KEY_TASKS][KEY_NORMAL_TASK][year][month]:
                    if len(data[KEY_TASKS][KEY_NORMAL_TASK][year][month][day]) == 0:
                        days_to_delete.append(day)
                for day in days_to_delete:
                    del data[KEY_TASKS][KEY_NORMAL_TASK][year][month][day]
                if len(data[KEY_TASKS][KEY_NORMAL_TASK][year][month]) == 0:
                    months_to_delete.append(month)
            for month in months_to_delete:
                del data[KEY_TASKS][KEY_NORMAL_TASK][year][month]
            if len(data[KEY_TASKS][KEY_NORMAL_TASK][year]) == 0:
                years_to_delete.append(year)

        for year in years_to_delete:
            del data[KEY_TASKS][KEY_NORMAL_TASK][year]

