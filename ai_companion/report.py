from health_memory import load_profile
from datetime import datetime


def generate_doctor_report():
    profile = load_profile()

    report = f"""
Health Summary Report
Date: {datetime.now().strftime("%Y-%m-%d")}

Name: {profile.get('name')}
Sleep (hours): {profile.get('sleep_hours_avg')}
Stress Level: {profile.get('stress_level')}
Conditions: {profile.get('conditions')}
Medications: {profile.get('medications')}
"""

    return report
