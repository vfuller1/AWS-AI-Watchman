#!/usr/bin/env python3
"""
AWS AI Watchman - Equipment Manual Generator
=============================================
Generates synthetic OEM-style service manuals (PDF) for each equipment
type in the synthetic fleet. Content is modelled on real CAT, Genie,
John Deere, Komatsu, and JLG documentation conventions.

Fault codes E001-E005 match the telemetry generator so the Knowledge
Base can return relevant procedures when the agent queries a fault code.

Usage:
    python generate_manuals.py --out-dir data/manuals
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

from fpdf import FPDF

# ---------------------------------------------------------------------------
# Fleet definitions -matches generate_telemetry.py equipment IDs
# ---------------------------------------------------------------------------
FLEET = [
    {
        "id": "CAT-EX",
        "model": "Caterpillar 320 Hydraulic Excavator",
        "engine": "Caterpillar C7.1 ACERT",
        "horsepower": "153 kW (205 HP) @ 1,800 RPM",
        "operating_weight": "21,300 kg (46,958 lb)",
        "max_dig_depth": "6,740 mm (22 ft 1 in)",
        "hydraulic_flow": "2 x 204 L/min @ 34.5 MPa",
        "fuel_capacity": "400 L (105.7 gal)",
        "hydraulic_oil_capacity": "210 L",
        "engine_oil_capacity": "30 L",
        "coolant_capacity": "42 L",
        "type": "Excavator",
    },
    {
        "id": "GEN-BL",
        "model": "Genie S-60 Telescopic Boom Lift",
        "engine": "Deutz D2011L03i (diesel) / 48V Electric (option)",
        "horsepower": "36.4 kW (48.8 HP)",
        "operating_weight": "8,845 kg (19,500 lb)",
        "platform_height": "18.3 m (60 ft)",
        "horizontal_reach": "12.5 m (41 ft)",
        "capacity": "227 kg (500 lb)",
        "hydraulic_oil_capacity": "95 L",
        "fuel_capacity": "90 L",
        "type": "Boom Lift",
    },
    {
        "id": "JD-BD",
        "model": "John Deere 850K Crawler Dozer",
        "engine": "John Deere PowerTech 6090H",
        "horsepower": "151 kW (202 HP) @ 1,800 RPM",
        "operating_weight": "18,734 kg (41,302 lb)",
        "blade_capacity": "4.59 m3 (6.0 yd3) -Semi-U blade",
        "hydraulic_flow": "163 L/min @ 27.6 MPa",
        "fuel_capacity": "364 L",
        "hydraulic_oil_capacity": "128 L",
        "engine_oil_capacity": "20 L",
        "type": "Bulldozer",
    },
    {
        "id": "KOM-FL",
        "model": "Komatsu FG25T-16 LPG Forklift",
        "engine": "Komatsu 4D94LE-2 / Mitsubishi G4E3 (LPG)",
        "horsepower": "40.5 kW (54.3 HP)",
        "rated_capacity": "2,500 kg (5,511 lb)",
        "lift_height": "3,000 mm (9.8 ft) standard / 5,500 mm max",
        "operating_weight": "3,720 kg (8,201 lb)",
        "hydraulic_oil_capacity": "22 L",
        "fuel": "LPG cylinder (18 kg)",
        "type": "Forklift",
    },
    {
        "id": "JLG-SC",
        "model": "JLG 2630ES Electric Scissor Lift",
        "engine": "Electric -24V DC (4 x 6V deep-cycle batteries)",
        "horsepower": "2.2 kW drive motor",
        "platform_height": "7.92 m (26 ft)",
        "capacity": "454 kg (1,000 lb)",
        "operating_weight": "1,814 kg (4,000 lb)",
        "battery_capacity": "210 Ah @ 24V",
        "hydraulic_oil_capacity": "15 L",
        "type": "Scissor Lift",
    },
]

# ---------------------------------------------------------------------------
# Fault code reference -E001-E005 match telemetry generator; extended set
# covers equipment-specific conditions.
# ---------------------------------------------------------------------------
FAULT_CODES = [
    {
        "code": "E001",
        "name": "Hydraulic Pressure Low",
        "severity": "HIGH",
        "description": (
            "System hydraulic pressure has dropped below the minimum operating threshold. "
            "This fault is triggered when pressure transducer P1 reads below 180 bar "
            "for more than 3 seconds during normal operation."
        ),
        "symptoms": [
            "Slow or unresponsive implement movement",
            "Warning light illuminated on instrument panel",
            "Audible alarm sequence: 2 short beeps",
            "Possible power de-rate to protect pump",
        ],
        "root_causes": [
            "Clogged hydraulic filter (primary -check first)",
            "Worn or failed hydraulic pump",
            "Internal relief valve stuck open or set too low",
            "Hydraulic oil level below MIN mark",
            "Suction line restriction or air ingestion",
            "Cold start in ambient temperatures below -10C",
        ],
        "diagnostic_steps": [
            "Check hydraulic oil level in sight glass -refill to MAX if below MIN",
            "Inspect hydraulic filter indicator -replace filter if differential > 2.5 bar",
            "Check all hydraulic hose connections for leaks or collapse",
            "Measure pump output pressure at test port TP1 -should be 210-240 bar at full throttle",
            "If pump output < 180 bar, proceed to pump pressure/flow test procedure (Section 4.3)",
            "Inspect main relief valve setting -adjust to 220 bar if out of spec",
        ],
        "resolution": (
            "Replace hydraulic filter if clogged. Top up fluid to MAX mark using approved "
            "HYDO Advanced 10 or equivalent 46-weight hydraulic oil. If pump pressure is "
            "below spec after filter replacement and fluid top-up, overhaul or replace pump. "
            "Clear fault code after repair; if fault recurs within 2 hours, escalate to "
            "hydraulic system specialist."
        ),
        "estimated_repair_time": "0.5 - 4 hours depending on root cause",
        "parts_required": "Hydraulic filter element (P/N HF-7723), hydraulic oil (as needed)",
    },
    {
        "code": "E002",
        "name": "Engine Coolant Temperature High",
        "severity": "CRITICAL",
        "description": (
            "Engine coolant temperature has exceeded 107C (225F). The ECM will initiate "
            "power de-rate at 105C and automatic shutdown at 112C to prevent engine damage."
        ),
        "symptoms": [
            "Engine temperature gauge in red zone",
            "Continuous alarm tone",
            "Progressive power loss (de-rate active)",
            "Visible steam from radiator area (severe cases)",
        ],
        "root_causes": [
            "Insufficient coolant level (most common -check immediately)",
            "Radiator core blocked by debris (mud, chaff, insects)",
            "Failed thermostat stuck closed",
            "Broken or slipping fan belt/serpentine belt",
            "Faulty coolant temperature sensor (false alarm -check sensor resistance)",
            "Head gasket failure (coolant loss into combustion chamber)",
            "Water pump impeller failure",
        ],
        "diagnostic_steps": [
            "IMMEDIATELY: shut down if temp > 110C. Allow 15 min cool-down before opening radiator",
            "Check coolant level in expansion tank -NEVER open cap when hot",
            "Inspect radiator fins for blockage -clean with compressed air from engine side",
            "Check fan belt condition and tension (deflection should be 10-15 mm under 10 kg load)",
            "Verify thermostat operation: remove and test in hot water -should open at 82-88C",
            "Check coolant for oil contamination (brown emulsion = head gasket suspect)",
        ],
        "resolution": (
            "Refill coolant to MAX using 50/50 mix of Caterpillar ELC or equivalent ASTM D6210. "
            "Clean or replace air filter to improve cooling airflow. Replace thermostat if stuck. "
            "Replace belt if worn or cracked. Head gasket failure requires certified technician. "
            "Do NOT restart until root cause is resolved."
        ),
        "estimated_repair_time": "0.5 - 8 hours (head gasket: 1-2 days)",
        "parts_required": "Coolant (as needed), thermostat (P/N TH-4421), drive belt (P/N DB-8832)",
    },
    {
        "code": "E003",
        "name": "Hydraulic System Fault",
        "severity": "HIGH",
        "description": (
            "A general hydraulic system fault has been detected. This code is set when the ECM "
            "detects an inconsistency between multiple hydraulic sensors (pressure, temperature, "
            "or flow) that does not match a specific E001 or E004 code pattern."
        ),
        "symptoms": [
            "Hydraulic function intermittent or inoperative",
            "Fault indicator on display",
            "Possible DTC stored in ECM memory",
            "Hydraulic oil temperature warning light",
        ],
        "root_causes": [
            "Hydraulic oil overheating (> 95C) -check oil cooler",
            "Failed solenoid valve on main control valve block",
            "Contaminated hydraulic oil (water ingestion or wear metals)",
            "Internal bypass in main control valve",
            "CAN bus communication fault between ECM and hydraulic control module",
        ],
        "diagnostic_steps": [
            "Connect diagnostic tool (Cat ET or equivalent) and retrieve active DTCs",
            "Check hydraulic oil temperature sensor reading -normal operating: 40-80C",
            "Collect hydraulic oil sample for analysis (ISO cleanliness target: 16/14/11)",
            "Test solenoid valve resistance at each valve connector (spec: 20-30 ohm at 20C)",
            "Inspect oil cooler bypass valve for proper operation",
            "Verify CAN bus termination resistance (should be 60 ohm between CAN H and CAN L)",
        ],
        "resolution": (
            "If oil contaminated (water or particles), drain and flush hydraulic system. "
            "Replace filter and fill with new oil. Replace faulty solenoid valves. "
            "Clean oil cooler fins if clogged. CAN bus faults require wiring harness inspection. "
            "Clear all DTCs and perform full system function test after repair."
        ),
        "estimated_repair_time": "1 - 6 hours",
        "parts_required": "Oil sample kit, hydraulic filter, solenoid valve (model-specific)",
    },
    {
        "code": "E004",
        "name": "Electrical / Sensor Fault",
        "severity": "MEDIUM",
        "description": (
            "An electrical fault has been detected in a sensor circuit, actuator, or the "
            "CAN bus network. May affect machine monitoring accuracy but does not always "
            "disable machine operation."
        ),
        "symptoms": [
            "One or more gauge readings showing -- or maximum value",
            "Intermittent warning lights",
            "Machine may enter limp-home mode",
            "DTC logged with sensor circuit ID",
        ],
        "root_causes": [
            "Damaged wiring harness (abrasion, pinching, rodent damage)",
            "Corroded or loose sensor connector",
            "Failed sensor (open circuit, short to ground)",
            "Blown fuse in sensor supply circuit",
            "Battery voltage below 11.5V (sensor supply under-voltage)",
            "ECM internal fault (rare)",
        ],
        "diagnostic_steps": [
            "Read DTCs using diagnostic tool to identify specific sensor circuit",
            "Check battery voltage -should be 12.4-12.8V (resting) / 13.8-14.4V (charging)",
            "Inspect fuse block -replace any blown fuse with correct amperage rating",
            "Visually inspect harness routing for abrasion against chassis or moving parts",
            "Disconnect suspect sensor and measure resistance to ground (should be > 10k ohm for open circuit check)",
            "Apply dielectric grease to connector before reassembly",
        ],
        "resolution": (
            "Replace faulty sensor. Repair or replace damaged wiring. Clean and secure "
            "connectors. Charge or replace battery if voltage is low. Wrap repaired harness "
            "sections with proper convoluted conduit and secure with cable ties. "
            "Clear DTCs and verify sensor reading returns to normal operating range."
        ),
        "estimated_repair_time": "0.5 - 3 hours",
        "parts_required": "Sensor (model-specific), wiring repair kit, fuse set",
    },
    {
        "code": "E005",
        "name": "Scheduled Maintenance Required",
        "severity": "LOW",
        "description": (
            "The machine has reached a scheduled maintenance interval. Service is required "
            "to maintain warranty coverage and prevent component wear. This fault does not "
            "affect machine performance but must be cleared by a qualified technician "
            "after service completion."
        ),
        "symptoms": [
            "MAINT indicator illuminated on instrument panel",
            "Hours-to-service counter shows 0 or negative",
            "Fault code logged in ECM service history",
        ],
        "root_causes": [
            "250-hour interval: engine oil and filter, fuel pre-filter",
            "500-hour interval: hydraulic filter, fuel filter (final), air filter check",
            "1000-hour interval: coolant test, drive belt inspection, battery service",
            "2000-hour interval: hydraulic oil analysis, undercarriage inspection (track machines)",
            "Annual: safety system test, ROPS/FOPS inspection",
        ],
        "diagnostic_steps": [
            "Check service meter reading in operator display or diagnostic tool",
            "Compare against maintenance schedule in Section 5 of this manual",
            "Determine which service interval items are due",
            "Gather required parts and fluids before beginning service",
        ],
        "resolution": (
            "Perform all maintenance tasks due at this interval per Section 5. "
            "Record service in the machine logbook. Use the diagnostic tool to reset "
            "the service interval counter after completion. Retain service records "
            "for warranty purposes."
        ),
        "estimated_repair_time": "1 - 4 hours depending on service interval",
        "parts_required": "See Section 5 maintenance schedule for interval-specific parts list",
    },
]

MAINTENANCE_SCHEDULE = [
    ("10 Hours / Daily", [
        "Walk-around inspection -check for leaks, loose hardware, damage",
        "Check engine oil level -add if below MIN",
        "Check coolant level in expansion tank",
        "Check hydraulic oil level in sight glass",
        "Inspect air pre-cleaner -empty if required",
        "Check fuel level -refuel before storage if below 1/4 tank",
        "Inspect tracks/tyres for wear and damage (as applicable)",
        "Test all warning lights and alarms (press test button)",
        "Clean cab glass and mirrors",
    ]),
    ("250 Hours (Monthly)", [
        "Change engine oil and filter (use approved 15W-40 or 10W-30 low-ash)",
        "Replace fuel pre-filter/water separator -drain water before removal",
        "Lubricate all grease points per lubrication diagram (Section 5.2)",
        "Inspect drive belts for wear, cracking, and tension",
        "Check battery terminals -clean and coat with protectant",
        "Inspect hydraulic hoses for abrasion and leaks",
        "Check all fluid levels and top up as required",
    ]),
    ("500 Hours (Quarterly)", [
        "All 250-hour tasks",
        "Replace hydraulic return filter element",
        "Replace engine air filter (or earlier if restriction indicator shows)",
        "Replace fuel final filter",
        "Inspect track/undercarriage components for wear (track machines)",
        "Check and adjust fan belt tension",
        "Inspect ROPS/FOPS structure for cracks or damage -DO NOT modify",
        "Test safety shutdown systems: high temp, low oil pressure",
        "Drain and clean fuel tank sediment bowl",
    ]),
    ("1,000 Hours (Semi-Annual)", [
        "All 500-hour tasks",
        "Take hydraulic oil sample for laboratory analysis",
        "Take engine oil sample (if not changed at 500 hrs)",
        "Inspect and test all safety devices and interlocks",
        "Check engine valve clearances (adjust if required)",
        "Inspect water pump, thermostat housing for seepage",
        "Lubricate all door hinges, latches, and access steps",
        "Check torque on all critical bolted joints (see torque chart Section 6)",
    ]),
    ("2,000 Hours (Annual)", [
        "All 1,000-hour tasks",
        "Complete hydraulic oil and filter change (sample results permitting)",
        "Change gear oil in final drives (track machines)",
        "Inspect and service hydraulic cylinders -check for scoring or seal leaks",
        "Replace coolant if ELC is not extended-life type",
        "Major undercarriage wear inspection and measurement",
        "Full electrical system check: ground straps, fuse ratings, harness condition",
        "Calibrate load management system (lifting equipment)",
        "Carry out annual safety inspection per regulatory requirements",
    ]),
]


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------
class EquipmentManual(FPDF):
    def __init__(self, equipment: dict):
        super().__init__()
        self.equipment = equipment
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=20, top=20, right=20)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, self.equipment["model"] + " -Service Manual", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_draw_color(180, 180, 180)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()} | CONFIDENTIAL -For Authorized Technicians Only", align="C")
        self.set_text_color(0, 0, 0)

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(30, 80, 160)
        self.set_text_color(255, 255, 255)
        self.cell(0, 9, "  " + title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def subsection_title(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(30, 80, 160)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.set_draw_color(30, 80, 160)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(2)

    def body(self, text: str):
        self.set_font("Helvetica", size=10)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet_list(self, items: list):
        self.set_font("Helvetica", size=10)
        for item in items:
            self.set_x(28)  # 20mm left margin + 8mm indent
            self.multi_cell(0, 6, "- " + item)

    def numbered_list(self, items: list):
        self.set_font("Helvetica", size=10)
        for i, item in enumerate(items, 1):
            self.set_x(28)
            self.multi_cell(0, 6, f"{i}. " + item)

    def warning_box(self, text: str, level: str = "WARNING"):
        colors = {
            "WARNING": (255, 200, 0),
            "DANGER": (220, 50, 50),
            "NOTICE": (0, 150, 220),
        }
        bg = colors.get(level, (255, 200, 0))
        self.ln(2)
        self.set_fill_color(*bg)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 7, f"  {level}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_fill_color(255, 250, 230)
        self.set_font("Helvetica", size=9)
        self.multi_cell(0, 6, "  " + text, fill=True)
        self.ln(2)

    # ------------------------------------------------------------------
    # Document sections
    # ------------------------------------------------------------------
    def cover_page(self):
        self.add_page()
        self.ln(20)
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(30, 80, 160)
        self.multi_cell(0, 14, self.equipment["model"], align="C")
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, "SERVICE AND MAINTENANCE MANUAL", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(8)
        self.set_draw_color(30, 80, 160)
        self.set_line_width(1)
        self.line(40, self.get_y(), 170, self.get_y())
        self.ln(8)
        self.set_font("Helvetica", size=11)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, f"Equipment Class: {self.equipment['type']}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 8, f"Serial Number Prefix: {self.equipment['id']}-XXX", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 8, f"Document Reference: SM-{self.equipment['id']}-2024", new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 8, f"Revision: 3.1 | Date: {datetime.now().strftime('%B %Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(12)
        self.warning_box(
            "This manual contains procedures that must be performed only by qualified technicians. "
            "Always follow all safety precautions. Failure to follow safety warnings may result in "
            "serious injury or death. Read all safety information before performing any maintenance.",
            level="DANGER"
        )
        self.set_text_color(0, 0, 0)

    def section_specifications(self):
        self.section_title("Section 1: Equipment Specifications")
        eq = self.equipment

        rows = []
        for key in ["engine", "horsepower", "operating_weight",
                    "hydraulic_oil_capacity", "fuel_capacity",
                    "hydraulic_flow", "max_dig_depth",
                    "platform_height", "capacity",
                    "rated_capacity", "lift_height", "blade_capacity"]:
            if key in eq:
                label = key.replace("_", " ").title()
                rows.append((label, eq[key]))

        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(220, 230, 245)
        self.cell(70, 8, "Specification", border=1, fill=True)
        self.cell(0, 8, "Value", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        fill = False
        self.set_font("Helvetica", size=10)
        for label, val in rows:
            self.set_fill_color(240, 245, 255) if fill else self.set_fill_color(255, 255, 255)
            self.cell(70, 7, label, border=1, fill=True)
            self.cell(0, 7, val, border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            fill = not fill

    def section_safety(self):
        self.section_title("Section 2: Safety Warnings and Precautions")
        self.warning_box(
            "LOCKOUT/TAGOUT: Before performing any maintenance, shut down the machine, "
            "lower all implements to the ground, apply the parking brake, and remove the key. "
            "Attach a lockout tag to the key switch. Allow the hydraulic system to depressurize "
            "(minimum 5 minutes after shutdown) before opening any hydraulic connections.",
            level="DANGER"
        )
        self.warning_box(
            "PERSONAL PROTECTIVE EQUIPMENT (PPE): Wear safety glasses, steel-toed boots, "
            "gloves rated for hydraulic oil, and hard hat at all times when working on this "
            "equipment. High-visibility vest required on active job sites.",
            level="WARNING"
        )
        self.body(
            "All maintenance must be performed in accordance with OSHA 29 CFR 1910.147 (Control "
            "of Hazardous Energy), OSHA 29 CFR 1910.178 (Powered Industrial Trucks -where "
            "applicable), and the manufacturer's recommended procedures in this manual."
        )
        self.subsection_title("2.1 Hydraulic System Safety")
        self.bullet_list([
            "Never open a hydraulic connection while the system is pressurized.",
            "Hydraulic oil under high pressure can penetrate skin and cause serious injury.",
            "Use a piece of cardboard -never your hand -to check for hydraulic leaks.",
            "Allow the system to cool below 50C before servicing hot hydraulic components.",
            "Dispose of used hydraulic oil in accordance with local environmental regulations.",
        ])
        self.subsection_title("2.2 Electrical System Safety")
        self.bullet_list([
            "Disconnect the negative battery terminal before working on the electrical system.",
            "Never bypass fuses or circuit breakers -investigate and repair the root cause.",
            "Keep all electrical connectors dry and clean -use dielectric grease on reassembly.",
            "Do not operate the machine if any wiring is exposed, frayed, or damaged.",
        ])

    def section_fault_codes(self):
        self.section_title("Section 3: Fault Code Reference")
        self.body(
            "The Electronic Control Module (ECM) monitors all critical machine systems and logs "
            "fault codes (Diagnostic Trouble Codes -DTCs) when a parameter falls outside its "
            "normal operating range. Fault codes can be read using a diagnostic display tool "
            "connected to the machine's CANbus diagnostic port (located in the operator cab).\n\n"
            "Fault codes remain active while the fault condition exists and are stored in ECM "
            "non-volatile memory for 50 hours after the fault clears. Always resolve the root "
            "cause before clearing fault codes -clearing without repair will result in fault "
            "recurrence and may mask additional damage."
        )
        for fc in FAULT_CODES:
            self.subsection_title(f"Fault Code {fc['code']} -{fc['name']} [{fc['severity']}]")
            self.body(fc["description"])
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, "Symptoms:", new_x="LMARGIN", new_y="NEXT")
            self.bullet_list(fc["symptoms"])
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, "Root Causes (most common first):", new_x="LMARGIN", new_y="NEXT")
            self.bullet_list(fc["root_causes"])
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, "Diagnostic Steps:", new_x="LMARGIN", new_y="NEXT")
            self.numbered_list(fc["diagnostic_steps"])
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, "Resolution:", new_x="LMARGIN", new_y="NEXT")
            self.body(fc["resolution"])
            self.set_font("Helvetica", "I", 10)
            self.cell(0, 6, f"Estimated repair time: {fc['estimated_repair_time']}", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 6, f"Parts typically required: {fc['parts_required']}", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)

    def section_maintenance(self):
        self.section_title("Section 5: Preventive Maintenance Schedule")
        self.body(
            "Adherence to the following maintenance schedule is mandatory for warranty coverage "
            "and to ensure safe, reliable operation. All service intervals are based on machine "
            "operating hours as displayed on the hour meter. Under severe conditions (dusty "
            "environments, extreme temperatures, continuous heavy loads) reduce intervals by 50%."
        )
        for interval, tasks in MAINTENANCE_SCHEDULE:
            self.subsection_title(interval)
            self.bullet_list(tasks)

    def section_troubleshooting(self):
        self.section_title("Section 4: Hydraulic System Troubleshooting")
        self.subsection_title("4.1 Hydraulic System Overview")
        self.body(
            "The hydraulic system consists of a variable-displacement axial piston pump, "
            "a main control valve (MCV) with individual sections for each actuator, "
            "hydraulic cylinders and motors for implements, and a return/filtration circuit. "
            "System pressure is monitored by multiple transducers and reported to the ECM. "
            "Operating pressure range: 180-240 bar (normal), 350 bar (relief valve setting)."
        )
        self.subsection_title("4.2 Slow or No Implement Response")
        self.numbered_list([
            "Verify fault codes -address any E001 or E003 codes first per Section 3",
            "Check hydraulic oil level -low level is the most common cause",
            "Check pump drive coupling for wear or failure",
            "Test pilot pressure at pilot manifold test port (TP2) -should be 35-40 bar",
            "Isolate suspect circuit by testing each implement individually",
            "Check for restriction in return line by measuring back-pressure at filter head",
        ])
        self.subsection_title("4.3 Hydraulic Pump Pressure/Flow Test")
        self.body(
            "Required equipment: calibrated pressure gauge (0-400 bar), flow meter (0-300 L/min), "
            "hydraulic test hoses, torque wrench.\n\nProcedure:"
        )
        self.numbered_list([
            "Warm the hydraulic system to operating temperature (minimum 50C oil temp)",
            "Connect pressure gauge to test port TP1 (pump outlet)",
            "Run engine at full throttle (rated RPM)",
            "Engage maximum load -stall condition if possible",
            "Record pressure: should be 210-240 bar. If < 180 bar, pump is worn",
            "Connect flow meter in series at pump outlet -compare to specification",
            "Flow below 90% of rated spec at rated pressure = pump overhaul required",
        ])
        self.warning_box(
            "Maximum working pressure during testing: 350 bar. Never exceed this limit. "
            "Wear full PPE including face shield during pressure testing.",
            level="DANGER"
        )

    def build(self, output_path: str):
        self.cover_page()
        self.add_page()
        self.section_specifications()
        self.section_safety()
        self.section_fault_codes()
        self.section_troubleshooting()
        self.section_maintenance()
        self.output(output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate synthetic equipment service manuals")
    parser.add_argument("--out-dir", default="scripts/ingest/data/manuals", help="Output directory")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating service manuals -> {out.resolve()}")
    generated = []
    for eq in FLEET:
        filename = f"{eq['id']}_service_manual.pdf"
        path = out / filename
        print(f"  Building {filename} ({eq['model']}) ...", end=" ", flush=True)
        manual = EquipmentManual(eq)
        manual.build(str(path))
        size_kb = path.stat().st_size / 1024
        print(f"OK ({size_kb:.0f} KB)")
        generated.append(path)

    print(f"\nOK  {len(generated)} manuals written to {out.resolve()}")
    print("    Upload with: python scripts/ingest/upload_to_bronze.py --data-dir", args.out_dir)


if __name__ == "__main__":
    main()
