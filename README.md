# MailPower

## Trigger email alerts based on APC UPS status info

### Configuration

Alert expressions are constructed using Python syntax and built-in keywords.  The keywords are also used within the email subject and body templates.  The keywords are as follows:
 - `online` `(bool)` : True if the UPS is online, False if it is not
 - `status` `(str)` : The status text (ONLINE, OFFLINE, ONBATT) from the UPS
 - `charge_pct` `(float)` : The percent charge remaining in the battery
 - `time_remaining_min` `(int)` : Estimated time remaining, in minutes
 - `date` `(datetime)` : UPS-provided date
 - `start_time` `(datetime)` : Time that UPS last came online
 - `line_voltage` `(float)` : Current line voltage reading
 - `load_pct` `(float)` : Current load percent
 - `battery_voltage` `(float)` : Current battery voltage
 - `ups_name` `(str)` : UPS name
 - `ups_model` `(str)` : UPS model
 - `ups_hostname` `(str)` : UPS hostname

### Example
```
    {
            "alertType" : 1,
            "alertExpression" : "not online and charge_pct < 99",
            "subject" : "Offline and power at {charge_pct}% {PROD}",
            "description" : "Server is offline and power is at {charge_pct}",
            "to" : "andy@test.com"
    }
```

### Running
`python MailPower.py`

When MailPower starts it will look for the "config.json" file.  A different config file can be provided using the `-c <config file path>` command-line argument. 
