import json
import os
import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from loguru import logger

TZ = ZoneInfo("Asia/Kolkata")

BASE_DIR = "/home/tanzo/Kyron_automation/KairoAI-Assistant/backend"
DATA_DIR = os.path.join(BASE_DIR, "data")
REMINDER_FILE = os.path.join(DATA_DIR, "reminders.json")


class ReminderManager:
    NUMBER_WORDS = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
    }

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.reminders = self.load()

    def load(self):
        if not os.path.exists(REMINDER_FILE):
            return []

        try:
            with open(REMINDER_FILE, "r", encoding="utf-8") as f:
                reminders = json.load(f)

            changed = False
            for item in reminders:
                if item.get("notifying") and not item.get("done"):
                    item["notifying"] = False
                    changed = True

            if changed:
                self.reminders = reminders
                self.save()

            return reminders
        except Exception as e:
            logger.error(f"Failed to load reminders: {e}")
            return []

    def save(self):
        try:
            with open(REMINDER_FILE, "w", encoding="utf-8") as f:
                json.dump(self.reminders, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    def add(self, remind_at: datetime, message: str, kind: str):
        item = {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "message": message,
            "remind_at": remind_at.isoformat(),
            "done": False,
        }

        self.reminders.append(item)
        self.save()

        logger.info(f"Added {kind}: {message} at {remind_at.isoformat()}")
        return item

    def due_items(self):
        now = datetime.now(TZ)
        due = []

        for item in self.reminders:
            if item.get("done"):
                continue

            if item.get("notifying"):
                continue

            remind_at = datetime.fromisoformat(item["remind_at"])

            if now >= remind_at:
                item["notifying"] = True
                due.append(item)

        if due:
            self.save()

        return due

    def mark_done(self, item_id: str):
        for item in self.reminders:
            if item.get("id") == item_id:
                item["done"] = True
                item["notifying"] = False
                self.save()
                return

    def mark_pending(self, item_id: str):
        for item in self.reminders:
            if item.get("id") == item_id:
                item["notifying"] = False
                self.save()
                return

    def parse_command(self, text: str):
        text = self._normalize_spoken_time(text.lower().strip())
        now = datetime.now(TZ)
        alarm_prefix = r"(?:set\s+(?:an?\s+|the\s+)?alarm|wake\s+me\s+up)"
        reminder_prefix = r"(?:remind\s+me|set\s+(?:a\s+|the\s+)?reminder)"
        number_pattern = r"(\d+)"
        unit_pattern = r"(seconds|second|secs|sec|minutes|minute|mins|min|hours|hour|hrs|hr)"

        # remind me in 10 minutes to check motor / set a reminder in 10 minutes to check motor
        match = re.search(
            rf"{reminder_prefix}\s+(?:in|after)\s+{number_pattern}\s*{unit_pattern}(?:\s+to)?(?:\s+(.*))?",
            text,
        )
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            message = (match.group(3) or "").strip() or "Reminder"

            remind_at = self._relative_time(now, value, unit)

            return {
                "kind": "reminder",
                "time": remind_at,
                "message": message,
            }

        # remind me of check motor in 10 minutes / remind me about payment after 20 sec
        match = re.search(
            rf"{reminder_prefix}\s+(?:of|about|to)?\s*(.*?)\s+(?:in|after)\s+{number_pattern}\s*{unit_pattern}\b",
            text,
        )
        if match:
            message = match.group(1).strip() or "Reminder"
            value = int(match.group(2))
            unit = match.group(3)

            remind_at = self._relative_time(now, value, unit)

            return {
                "kind": "reminder",
                "time": remind_at,
                "message": message,
            }

        # set alarm in 10 minutes / set an alarm after 10 minutes / wake me up in 10 minutes
        match = re.search(
            rf"{alarm_prefix}\s+(?:in|after|for)\s+{number_pattern}\s*{unit_pattern}\b",
            text,
        )
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            alarm_at = self._relative_time(now, value, unit)

            return {
                "kind": "alarm",
                "time": alarm_at,
                "message": "Alarm",
            }

        # set alarm for 7 am / set an alarm at 7:30 pm / wake me up at 7.30 p.m.
        match = re.search(
            rf"{alarm_prefix}\s+(?:for|at)\s+(\d{{1,2}})(?:(?::|\.|\s+)(\d{{1,2}}))?\s*(a\.?m\.?|p\.?m\.?)?",
            text,
        )
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            ampm = match.group(3).replace(".", "") if match.group(3) else None

            alarm_at = self._clock_time(now, hour, minute, ampm)

            return {
                "kind": "alarm",
                "time": alarm_at,
                "message": "Alarm",
            }

        # remind me at 6 pm / set a reminder at 6.30 p.m. to call customer
        match = re.search(
            rf"{reminder_prefix}\s+at\s+(\d{{1,2}})(?:(?::|\.|\s+)(\d{{1,2}}))?\s*(a\.?m\.?|p\.?m\.?)?(?:\s+to)?\s+(.*)",
            text,
        )
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            ampm = match.group(3).replace(".", "") if match.group(3) else None
            message = match.group(4).strip() or "Reminder"

            remind_at = self._clock_time(now, hour, minute, ampm)

            return {
                "kind": "reminder",
                "time": remind_at,
                "message": message,
            }

        return None

    def _normalize_spoken_time(self, text: str) -> str:
        text = text.replace("-", " ")
        text = re.sub(r"\b(\d+)\s*(sec|secs|min|mins|hr|hrs)\b", r"\1 \2", text)
        text = re.sub(r"\bo\s+clock\b", " ", text)
        text = re.sub(r"\ba\s*m\b", "am", text)
        text = re.sub(r"\bp\s*m\b", "pm", text)
        text = re.sub(r"\ba\.m\.\b", "am", text)
        text = re.sub(r"\bp\.m\.\b", "pm", text)

        words = text.split()
        normalized = []
        i = 0

        while i < len(words):
            one_word = self._number_word_value(words[i])
            two_word = None

            if i + 1 < len(words):
                two_word = self._number_word_value(f"{words[i]} {words[i + 1]}")

            if two_word is not None:
                normalized.append(str(two_word))
                i += 2
                continue

            if one_word is not None:
                normalized.append(str(one_word))
                i += 1
                continue

            normalized.append(words[i])
            i += 1

        text = " ".join(normalized)
        text = re.sub(r"\b(\d{1,2})\s+(?:o|oh|zero|0)\s+(\d)\b", r"\1 0\2", text)
        return text

    def _number_word_value(self, text: str):
        parts = text.split()

        if len(parts) == 1:
            return self.NUMBER_WORDS.get(parts[0])

        if len(parts) == 2:
            tens = self.NUMBER_WORDS.get(parts[0])
            ones = self.NUMBER_WORDS.get(parts[1])
            if tens in {20, 30, 40, 50} and ones is not None and 0 < ones < 10:
                return tens + ones

        return None

    def looks_like_reminder_command(self, text: str) -> bool:
        text = text.lower().strip()
        return bool(
            re.search(r"\b(?:set|create|add)\s+(?:an?\s+|the\s+)?alarm\b", text)
            or re.search(r"\bwake\s+me\s+up\b", text)
            or re.search(r"\bremind\s+me\b", text)
        )

    def _relative_time(self, now: datetime, value: int, unit: str):
        if unit in {"second", "seconds", "sec", "secs"}:
            return now + timedelta(seconds=value)

        if unit in {"minute", "minutes", "min", "mins"}:
            return now + timedelta(minutes=value)

        return now + timedelta(hours=value)

    def _clock_time(self, now: datetime, hour: int, minute: int, ampm: str | None):
        if minute < 0 or minute > 59:
            raise ValueError(f"Invalid minute: {minute}")

        if ampm:
            if hour < 1 or hour > 12:
                raise ValueError(f"Invalid 12-hour clock hour: {hour}")

            if ampm == "pm" and hour != 12:
                hour += 12

            if ampm == "am" and hour == 12:
                hour = 0
        else:
            if hour < 0 or hour > 23:
                raise ValueError(f"Invalid 24-hour clock hour: {hour}")

            candidate_hours = [hour]

            if 1 <= hour <= 11:
                candidate_hours.append(hour + 12)
            elif hour == 12:
                candidate_hours.append(0)

            candidates = []
            for candidate_hour in candidate_hours:
                candidate = now.replace(
                    hour=candidate_hour,
                    minute=minute,
                    second=0,
                    microsecond=0,
                )
                if candidate <= now:
                    candidate += timedelta(days=1)
                candidates.append(candidate)

            return min(candidates)

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target <= now:
            target += timedelta(days=1)

        return target
