#!/usr/bin/env python3
"""
Worked example: the four Cascadia board dashboards for sunlink (TEL, MDI, DRD, STR).

    python sunlink_cascadia.py <sunlink>/dashboards/PROD

Signal names, scaling and fault limits come from sunlink dbc/cascadia.dbc and firmware_v4
(origin/main, 2026-10-31):
  TEL/DRD MCU health: undervoltage < 2000 mV, overtemp > 125 degC (driver/mcu_health_driver.h)
  STR MCU health:     undervoltage < 2400 mV, overtemp > 105 degC (app/diagnostic_app.c)
  MDI motor temp:     overtemp set at 100 degC, cleared at 95 degC (app/diagnostic.h/.c)

Task analysis (Endsley levels), shared by every board:
  L1 perceive   is the board alive and talking? any fault bit set? current values
  L2 comprehend is a value inside its normal band? did the board reset? is an input stuck?
  L3 project    is a temperature/voltage trending toward its limit? (trend + band)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from hmi_grafana import (BLUE, DARK, GREY, NO_YES, OFF_ON, OK_FAULT, ORANGE, RED, Board, Dash,  # noqa: E402
                         geomap, stat, steps, timeline, trend, value_map)

TAGS = ["cascadia", "prod"]
CAR = "Cascadia"


def mcu_health(b: Board, d: Dash, cls: str, v_field: str, t_field: str, uv_mv: int, ot_c: int, w: int = 4):
    d.add(stat(b.t("MCU Vdd", "mV"), b.q(cls, v_field), "suffix: mV", steps((None, RED), (uv_mv, GREY)), decimals=0,
               description=f"{v_field}: MCU supply. Red below {uv_mv} mV, where firmware sets the undervoltage flag. "
                           "0 means the ADC read failed."), w=w, h=5)
    d.add(stat(b.t("MCU temperature", "°C"), b.q(cls, t_field), "celsius", steps((None, GREY), (ot_c, RED)),
               decimals=0, description=f"{t_field}: MCU die temperature. Red at {ot_c} °C, where firmware sets the "
                                       "overtemperature flag."), w=w, h=5)


# ----------------------------------------------------------------------------- TEL
def tel() -> Dash:
    b = Board("TEL")
    d = Dash(f"PROD: TEL - {CAR}", "cascadia-prod-tel", TAGS,
             "Telemetry board: link health, GPS position/status/motion, IMU. Health and faults first, detail below.")
    d.row("Health & faults")
    d.add(b.freshness("TELTimeSinceBootup"), w=4, h=5)
    d.add(b.uptime("TELTimeSinceBootup", "TELTimeSinceBootUp"), w=4, h=5)
    mcu_health(b, d, "TELMCUHealth", "MCU_Voltage", "MCU_Temperature", 2000, 125)
    d.add(stat(b.t("CAN bus load", "%"), b.q("CANBusLoad", "BusLoad"), "percent",
               steps((None, GREY), (70, ORANGE), (90, RED)), decimals=0, vmin=0, vmax=100,
               description="BusLoad measured by TEL. Orange from 70 %, red from 90 % (frames start to be delayed)."),
          w=4, h=5)
    d.add(stat(b.t("GPS fix"), b.q("TELGpsStatus", "GpsFixType", "last"), "none",
               mappings=value_map(GPS_FIX), sparkline=False,
               description="GpsFixType. Only 3D fix is normal; anything else is shown in orange with its name."),
          w=4, h=5)
    b.fault_block(d, "TELDiagnostics", ["TELWatchdogReset", "IMUReadFail", "IMUWriteFail", "GPSReadFail",
                                      "GPSWriteFail", "MCUOvertemp", "MCUUndervoltage"],
                   description="TELDiagnostics bits (max per window, so a single faulted frame is never averaged away).", w=24, h=6)

    d.row("GPS position & status")
    d.add(geomap(b.t("GPS track"), "TEL", "TELGpsPosition", "GpsLatitude", "GpsLongitude",
                 description="GpsLatitude/GpsLongitude (deg). TEL only sends a position when the receiver has a fix."),
          w=12, h=14)
    d.add(timeline(b.t("GPS status"), [
        (b.q("TELGpsStatus", "GpsFixType", "last"), GPS_FIX),
        (b.q("TELGpsStatus", ["GpsFixOk"], "min"), {0: ("NO FIX", ORANGE), 1: ("FIX OK", GREY)}),
        (b.q("TELGpsStatus", ["GpsDiffCorrections", "GpsUtcTimeValid", "GpsUtcDateValid", "GpsUtcTimeResolved"],
             "min"), NO_YES),
    ], description="Fix type and receiver flags from TELGpsStatus. Orange only when there is no usable fix."),
          w=12, h=6)
    d.add(trend(b.t("GPS satellites", "count"), b.q("TELGpsStatus", ["GpsSatsUsed", "GpsSatsHeard"], "last"),
                "suffix: sats", vmin=0, limits={"low": 4},
                description="Satellites used in the solution vs heard. Fewer than 4 used cannot give a 3D fix."),
          w=6, h=8)
    d.add(trend(b.t("GPS horizontal accuracy", "m"), b.q("TELGpsStatus", "GpsHorizAccuracy"), "lengthm", vmin=0,
                limits={"caution_high": 5, "high": 20}, decimals=1,
                description="Receiver's horizontal accuracy estimate. Orange above 5 m, red above 20 m."),
          w=6, h=8)

    d.row("GPS motion")
    d.add(trend(b.t("GPS ground speed", "km/h"), b.q("TELGpsMotion", "GpsGroundSpeed"), "velocitykmh", vmin=0,
                decimals=1, description="GpsGroundSpeed from the receiver (independent of the motor controller)."),
          w=8, h=7)
    d.add(trend(b.t("GPS heading", "°"), b.q("TELGpsMotion", "GpsHeading", "last"), "degree", vmin=0, vmax=360,
                decimals=0, description="GpsHeading, 0 = north, clockwise."), w=8, h=7)
    d.add(trend(b.t("GPS altitude", "m"), b.q("TELGpsMotion", "GpsAltitude"), "lengthm", decimals=1,
                description="GpsAltitude above mean sea level."), w=8, h=7)
    d.add(trend(b.t("GPS PDOP"), b.q("TELGpsStatus", "GpsPDOP"), "none", vmin=0, decimals=2,
                limits={"caution_high": 2.5, "high": 6},
                description="Position dilution of precision (dimensionless). Under 2.5 is good; orange above 2.5, "
                            "red above 6."), w=8, h=7)
    d.add(stat(b.t("GPS UTC time"), b.q("TELGpsUtcTime", ["GpsHour", "GpsMinute", "GpsSecond"], "last"), "none",
               decimals=0, sparkline=False, description="UTC time from the receiver (h, min, s). Check it against "
                                                        "GpsUtcTimeValid in GPS status before trusting it."),
          w=8, h=7)
    d.add(trend(b.t("GPS date"), b.q("TELGpsUtcTime", ["GpsYear", "GpsMonth", "GpsDay"], "last"), "none",
                decimals=0, description="UTC date from the receiver."), w=8, h=7)

    d.row("IMU")
    d.add(trend(b.t("IMU acceleration", "m/s²"), b.q_multi([("TELImuAG_X", "ImuAGXAccel"), ("TELImuAGY", "ImuAGYAccel"),
                                                           ("TELImuAGZ", "ImuAGZAccel")]),
                "accMS2", decimals=2, description="Linear acceleration, X/Y/Z."), w=8, h=8)
    d.add(trend(b.t("IMU angular rate", "rad/s"), b.q_multi([("TELImuAG_X", "ImuAGXGyro"), ("TELImuAGY", "ImuAGYGyro"),
                                                            ("TELImuAGZ", "ImuAGZGyro")]),
                "rotrads", decimals=3, description="Gyroscope, X/Y/Z."), w=8, h=8)
    d.add(trend(b.t("IMU magnetic field", "µT"), b.q_multi([("TELImuMX", "ImuMXMag"), ("TELImuMY", "ImuMYMag"),
                                                           ("TELImuMZ", "ImuMZMag")]),
                "suffix: µT", decimals=1, description="Magnetometer, X/Y/Z."), w=8, h=8)
    return d


GPS_FIX = {0: ("NO FIX", ORANGE), 1: ("DEAD RECKONING", ORANGE), 2: ("2D FIX", ORANGE), 3: ("3D FIX", GREY),
           4: ("GNSS + DR", GREY), 5: ("TIME ONLY", ORANGE)}


# ----------------------------------------------------------------------------- MDI
def mdi() -> Dash:
    b = Board("MDI")
    d = Dash(f"PROD: MDI - {CAR}", "cascadia-prod-mdi", TAGS,
             "Motor driver interface: link health, faults and the motor RTD temperature.")
    d.row("Health & faults")
    d.add(b.freshness("MDITimeSinceBootup"), w=6, h=5)
    d.add(b.uptime("MDITimeSinceBootup", "MDITimeSinceBootUp"), w=6, h=5)
    d.add(stat(b.t("Motor temperature", "°C"), b.q("MDIMotorTemperature", "MotorTemperature"), "celsius",
               steps((None, GREY), (95, ORANGE), (100, RED)), decimals=0,
               description="RTD motor temperature. Orange from 95 °C (overtemp clears here), red at 100 °C "
                           "(firmware sets MDIMotorOverTemp)."), w=6, h=5)
    d.add(stat(b.t("RTD read"), b.q("MDIMotorTemperature", "RTDReadSuccess", "min"), "none",
               mappings=value_map({0: ("FAILED", RED), 1: ("OK", GREY)}), sparkline=False,
               description="RTDReadSuccess (worst in window). FAILED means the temperature above is not valid."),
          w=6, h=5)
    b.fault_block(d, "MDIDiagnostics", ["MDIWatchdogReset", "MDIVoltageOverThreshold", "MDIMotorOverTemp",
                                      "MDIRTDFault", "MDIRTDCommError"],
                   description="MDIDiagnostics bits. MDIVoltageOverThreshold is defined but not set by current "
                               "MDI firmware, so it always reads OK.", w=24, h=6)
    d.row("Motor temperature")
    d.add(trend(b.t("Motor temperature", "°C"), b.q("MDIMotorTemperature", "MotorTemperature"), "celsius",
                limits={"caution_high": 95, "high": 100}, decimals=0, vmin=0,
                description="Trend against the overtemp band (95 °C clear / 100 °C set). Watch the slope to "
                            "see the limit coming."), w=16, h=9)
    d.add(timeline(b.t("RTD read"), b.q("MDIMotorTemperature", ["RTDReadSuccess"], "min"),
                   {0: ("READ FAIL", RED), 1: ("OK", GREY)},
                   description="RTDReadSuccess (worst in window). READ FAIL means the temperature is not valid."),
          w=8, h=4)
    d.add(timeline(b.t("RTD fault flags"), b.q("MDIMotorTemperature", ["RTDFaultFlags"], "max"),
                   {0: ("NONE", GREY), 4: ("OV/UV", RED), 64: ("RTD LOW", RED), 128: ("RTD HIGH", RED)},
                   description="MAX31865 fault register: 0x80 RTD high (open), 0x40 RTD low (short), "
                               "0x04 over/undervoltage. Other values: several bits at once (UNKNOWN)."),
          w=8, h=5, below=True)
    return d


# ----------------------------------------------------------------------------- DRD
def drd() -> Dash:
    b = Board("DRD")
    d = Dash(f"PROD: DRD - {CAR}", "cascadia-prod-drd", TAGS,
             "Driver dashboard: link health, faults, pedal/drive inputs and the motor command sent to MDI.")
    d.row("Health & faults")
    d.add(b.freshness("DRDTimeSinceBootup"), w=4, h=5)
    d.add(b.uptime("DRDTimeSinceBootup", "DRDTimeSinceBootUp"), w=4, h=5)
    mcu_health(b, d, "DRDMCUHealth", "DRDMCUSupplyVoltage", "DRDMCUTemperature", 2000, 125)
    d.add(stat(b.t("Drive state"), b.q("DRDDiagnostics", "DriveState", "last"), "none",
               mappings=value_map(DRIVE_STATE), sparkline=False,
               description="DriveState as DRD sees it."), w=4, h=5)
    d.add(stat(b.t("SOC", "%"), b.q("DRDDiagnostics", "SOC", "last"), "percent", decimals=0, vmin=0, vmax=104,
               description="State of charge shown to the driver (can read up to 104 %, SOC_MAX = 1.04)."), w=4, h=5)
    b.fault_block(d, "DRDDiagnostics", ["ADCOutOfRange", "ADCMismatch", "DRDWatchdogReset", "MotorCommFault",
                                      "DRDMCUOverTemp", "DRDMCUUnderVoltage"],
                   description="DRDDiagnostics fault bits.", w=12, h=6, tile_w=4)
    d.add(timeline(b.t("Cyclic data timeouts"),
                   b.q("DRDDiagnostics", ["SpeedTimeout", "DriveStateTimeout", "SOCTimeout", "VoltageTimeout",
                                          "CurrentTimeout", "AccelTimeout"], "max"),
                   {0: ("OK", GREY), 1: ("TIMEOUT", ORANGE)},
                   description="A cyclic input DRD displays stopped arriving, so the LCD shows stale data."),
          w=12, h=6)
    d.row("Driver inputs & motor command")
    d.add(trend(b.t("Throttle & regen command", "DAC counts"), b.q("MotorCommand", ["ThrottleDAC", "RegenDAC"]),
                "suffix: counts", vmin=0, vmax=1023, decimals=0,
                description="MotorCommand DAC values sent to MDI (0 to 1023; MDI caps throttle at 920)."),
          w=12, h=8)
    d.add(timeline(b.t("Driver state"), [
        (b.q("DRDDiagnostics", ["DriveState"], "last"), DRIVE_STATE),
        (b.q("MotorCommand", ["Direction"], "last"), {0: ("REVERSE", BLUE), 1: ("FORWARD", DARK)}),
        (b.q("MotorCommand", ["EcoModeOn"], "last"), {0: ("POWER", BLUE), 1: ("ECO", DARK)}),
        (b.q("MotorCommand", ["SpeedUnits"], "last"), {0: ("MPH", BLUE), 1: ("KPH", DARK)}),
        (b.q("DRDDiagnostics", ["BrakePressed", "RegenEnabled"], "max"), OFF_ON),
    ], description="Drive mode and driver inputs. Blue marks the less common or active state."), w=12, h=8)
    d.row("Pedal sensor & SOC")
    d.add(trend(b.t("Throttle pedal raw ADC", "counts"), b.q("DRDDiagnostics", ["RawADC1", "RawADC2"]),
                "suffix: counts", vmin=0, decimals=0,
                description="Both throttle sensor channels. They should track each other; a gap means ADCMismatch."),
          w=12, h=7)
    d.add(trend(b.t("SOC", "%"), b.q("DRDDiagnostics", "SOC", "last"), "percent", vmin=0, vmax=104, decimals=0,
                description="SOC as displayed on the driver LCD."), w=12, h=7)
    return d


DRIVE_STATE = {0: ("INVALID", RED), 1: ("FORWARD", GREY), 2: ("CRUISE", BLUE), 3: ("PARK", DARK),
               4: ("REVERSE", BLUE)}


# ----------------------------------------------------------------------------- STR
def strd() -> Dash:
    b = Board("STR")
    d = Dash(f"PROD: STR - {CAR}", "cascadia-prod-str", TAGS,
             "Steering wheel: link health, faults, button/switch states and cruise set speed.")
    d.row("Health & faults")
    d.add(b.freshness("STRTimeSinceBootup"), w=6, h=5)
    d.add(b.uptime("STRTimeSinceBootup", "STRTimeSinceBootUp"), w=6, h=5)
    mcu_health(b, d, "STRMCUHealth", "STRMCUVoltage", "STRMCUTemperature", 2400, 105, w=6)
    b.fault_block(d, "STRFlags", ["STRMCUUnderVoltage", "STRMCUOverTemp"],
                   description="STRFlags. Current STR firmware has no watchdog-reset flag "
                               "(STRDiagnostics 0x582 is not sent).", w=24, h=4)
    d.row("Driver controls")
    d.add(timeline(b.t("Buttons & switches"),
                   b.q("STRDRDControl", ["STRRegenEnabled", "STRCruiseEnabled", "STRLeftTurnSignalEnabled",
                                         "STRRightTurnSignalEnabled", "STRHornEnabled", "STRPushToTalkEnabled",
                                         "STRLCDScreenNextPage", "STRCruiseIncrement", "STRCruiseDecrement"], "max"),
                   OFF_ON, description="STRDRDControl inputs (max per window so short presses still show)."),
          w=16, h=10)
    d.add(trend(b.t("Cruise set speed", "km/h"), b.q("STRDRDControl", "STRCruiseSetVelocity", "last"),
                "velocitykmh", vmin=0, decimals=0, description="STRCruiseSetVelocity requested by the driver."),
          w=8, h=10)
    return d


BUILDERS = {"TEL": tel, "MDI": mdi, "DRD": drd, "STR": strd}

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for board, build in BUILDERS.items():
        path = out / f"PROD_{board}_{CAR}.json"
        build().write(path)
        print("wrote", path)
