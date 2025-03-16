import math
import json
import signal
import subprocess
import sys
import time
import datetime
import smtplib
import re

Done = False
def handle_death(sig, frame):
    global Done
    print("Exiting")
    Done = True

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class ApcStatus:
    online: bool = True
    status: str = None
    charge_pct: float = 0.0
    time_remaining_min: int = 0
    date: datetime = None
    start_time: datetime = None
    line_voltage: float = 0.0
    load_pct: float = 0.0
    battery_voltage: float = 0.0
    ups_name: str = None
    ups_model: str = None
    ups_hostname: str = None
    def __str__(self):
        lines: list[str] = []
        for key, value in vars(self).items():
            lines.append(f"{key} : {value}\n")
        return ''.join(lines)

class MailPowerSmtpConfigration:
    host: str = "localhost"
    port: int = 25
    from_addr: str = None
    to_addr: str = None
    def __init__(self, smtpConfig: dict):
        if "host" in smtpConfig and smtpConfig["host"]:
            self.host = smtpConfig["host"]
        if "port" in smtpConfig and smtpConfig["port"]:
            self.port = smtpConfig["port"]
        if "from" in smtpConfig and smtpConfig["from"]:
            self.from_addr = smtpConfig["from"]
        if "to" in smtpConfig and smtpConfig["to"]:
            self.to_addr = smtpConfig["to"]

        if self.from_addr is None:
            raise TypeError("Must provide from address")

class MailPowerAlert:
    expression: str = None
    type: int = 0
    def __init__(self, type: int):
        self.type = type
    def trigger(self, curstatus: ApcStatus):
        pass

class MailPowerEmailAlertConfig(MailPowerAlert):
    __subject_template__: str = None
    __description_template__: str = None
    __to__: str = None
    def __init__(self, config_data : dict, default_to: str = None):
        super().__init__(1)
        if default_to is not None:
            self.__to__ = default_to
        if "alertExpression" in config_data:
            self.expression = config_data["alertExpression"]
        if "subject" in config_data:
            self.__subject_template__ = config_data["subject"]
        if "description" in config_data:
            self.__description_template__ = config_data["description"]
        if "to" in config_data:
            self.__to__ = config_data["to"]

        if self.expression is None:
            raise ValueError("Must provide alert expression")
        if self.__to__ is None:
            raise ValueError("Must provide email recipient")

    def trigger(self, curstatus: ApcStatus):
        mailer.send(alert.__to__, MailTemplater().produce(curstatus, self.__subject_template__), MailTemplater().produce(curstatus, self.__description_template__))

class MailPowerConfiguration:
    __config_file__: str = None
    test_mode: bool = False
    test_file: str = None
    poll_time_sec: int = 30
    send_freq_min: int = 30
    smtp_config: MailPowerSmtpConfigration
    disable_smtp: bool = False
    alerts: list[MailPowerAlert] = []

    def __init__(self, config_file: str):
        self.__config_file__ = config_file
        self.reload()

    def reload(self):
        self.__reset__()
        with open(self.__config_file__, 'r') as file:
            data = json.load(file)
        if "testFile" in data and data["testFile"]:
            self.test_mode = True
            self.test_file = data["testFile"]
        if "pollFreqSec" in data:
            self.poll_time_sec = data["pollFreqSec"]
        if "sendMinFreqMin" in data:
            self.send_freq_min = data["sendMinFreqMin"]
        if "smtp" in data:
            self.smtp_config = MailPowerSmtpConfigration(data["smtp"])
        if "disableSmtp" in data:
            self.disable_smtp = data["disableSmtp"]
        if "alerts" in data:
            for alert_item in data["alerts"]:
                if alert_item["alertType"] == 1:
                    self.alerts.append(MailPowerEmailAlertConfig(alert_item, self.smtp_config.to_addr))

    def __reset__(self):
        self.test_mode = False
        self.test_file = None
        self.poll_time_sec = 30
        self.send_freq_min = 30
        self.smtp_config = None
        self.alerts = []

class ExpEvaluator:
    __status_dic__: dict = {}
    def __init__(self, st: ApcStatus):
        for key, value in vars(st).items():
            self.__status_dic__[key] = value
    def evaluates_true(self, config: MailPowerAlert):
        return eval(config.expression, {}, self.__status_dic__)

class ApcStatusTextGetter:
    @staticmethod
    def __get_status_file__(sample_file: str):
        with open(sample_file, 'r') as file:
            return file.read()
    @staticmethod
    def __get_status_cmd__():
        result = subprocess.run("apcaccess", capture_output=True, text=True, shell=True)
        return result.stdout
    @staticmethod
    def get_status_text(sample_file: str = None):
        if sample_file is None:
            return ApcStatusTextGetter.__get_status_cmd__()
        return ApcStatusTextGetter.__get_status_file__(sample_file)

class ApcStatusParser:
    __config__: MailPowerConfiguration = None
    def __init__(self, config: MailPowerConfiguration):
        self.__config__ = config

    def get_status(self) -> ApcStatus:
        self.status = ApcStatus()
        for line in ApcStatusTextGetter().get_status_text(self.__config__.test_file).splitlines():
             parts = line.split(":", 1)
             key = parts[0].strip()
             value = parts[1].strip()
             match key:
                case "STATUS":
                    self.__parse_status__(value)
                case "BCHARGE":
                    self.__parse_charge__(value)
                case "TIMELEFT":
                    self.__parse_time_remaining__(value)
                case "DATE":
                     self.__parse_date__(value)
                case "STARTTIME":
                     self.__parse_start_time__(value)
                case "LINEV":
                     self.__parse_line_volt__(value)
                case "LOADPCT":
                     self.__parse_load_pct__(value)
                case "BATTV":
                     self.__parse_batt_vlt__(value)
                case "UPSNAME":
                     self.__parse_ups_name__(value)
                case "MODEL":
                     self.__parse_ups_model__(value)
                case "HOSTNAME":
                     self.__parse_ups_hostname__(value)

        return self.status

    def __parse_status__(self, data: str):
        self.status.online = (data == "ONLINE")
        self.status.status = data
    def __parse_charge__(self, data: str):
        self.status.charge_pct = float(data.split(" ")[0])
    def __parse_time_remaining__(self, data: str):
        self.status.time_remaining_min = math.floor(float(data.split(" ")[0]))
    def __parse_date__(self, data: str):
        self.status.date = datetime.datetime.fromisoformat(data)
    def __parse_start_time__(self, data: str):
        self.status.start_time = datetime.datetime.fromisoformat(data)
    def __parse_line_volt__(self, data: str):
        self.status.line_voltage = float(data.split(" ")[0])
    def __parse_load_pct__(self, data: str):
        self.status.load_pct = float(data.split(" ")[0])
    def __parse_batt_vlt__(self, data: str):
        self.status.battery_voltage = float(data.split(" ")[0])
    def __parse_ups_name__(self, data: str):
        self.status.ups_name = data
    def __parse_ups_model__(self, data: str):
        self.status.ups_model = data
    def __parse_ups_hostname__(self, data: str):
        self.status.ups_hostname = data

class ShouldSendChecker:
    config: MailPowerConfiguration
    def __init__(self, config: MailPowerConfiguration):
        self.config = config
    def should_send(self):
        try:
            with open("lastsent", "r") as file:
                lastsenttime = file.readline().strip()
                lastsentdatetime = datetime.datetime.fromisoformat(lastsenttime)
                if self.config.send_freq_min <= 0 or ((datetime.datetime.now() - lastsentdatetime).total_seconds() / 60 > self.config.send_freq_min):
                    self.__write_time_file__()
                    return True
                return False
        except FileNotFoundError:
            self.__write_time_file__()
    def __write_time_file__(self):
        with open("lastsent", "w") as file:
                file.write(datetime.datetime.now().isoformat())

class MailTemplater:
    @staticmethod
    def __do_repl__(match: re.Match[str], status: ApcStatus):
        templstr = match.group(0).strip("{}")
        if templstr in vars(status):
            return str(vars(status)[templstr])
        return match.group(0)
    @staticmethod
    def produce(status: ApcStatus, text: str):
        return re.sub(r"\{[a-z\_]*\}", lambda match: MailTemplater.__do_repl__(match, status), text)

class Mailer:
    __config__ : MailPowerConfiguration = None
    def __init__(self, config: MailPowerConfiguration):
        self.__config__ = config
    def send(self, to: str, subject: str, description: str):
        emailtext = f"Subject: {subject}\r\n{description}"
        if self.__config__.disable_smtp:
            print(f"Would send email to {to}:\n----------------\n{emailtext}\n----------------\n")
        else:
            __mailer__ = smtplib.SMTP(self.__config__.smtp_config.host, self.__config__.smtp_config.port)
            __mailer__.sendmail(self.__config__.smtp_config.from_addr, to, emailtext)
            __mailer__.quit()

config_file = "config.json"
arg_iter = iter(sys.argv[1:])
for arg in arg_iter:
    if (arg == "-c"):
        config_file = next(arg_iter)
        print(f"Using config file '{config_file}'")
    if (arg == "--dump-params"):
        config = MailPowerConfiguration(config_file)
        parser = ApcStatusParser(config)
        print(parser.get_status())
        exit()

signal.signal(signal.SIGINT, handle_death)
config = MailPowerConfiguration(config_file)
parser = ApcStatusParser(config)
checker = ShouldSendChecker(config)
mailer = Mailer(config)
while not Done:
    try:
        config.reload()
        curstatus = parser.get_status()
        evaluator = ExpEvaluator(curstatus)
        for alert in config.alerts:
            if evaluator.evaluates_true(alert) and checker.should_send():
                alert.trigger(curstatus)
    except Exception as e:
        eprint(f"MailPower failed: {e}")
        if e is TypeError:
            Done = True

    time.sleep(config.poll_time_sec)

