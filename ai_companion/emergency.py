from health_memory import get_emergency_contact


def trigger_emergency():
    contact = get_emergency_contact()

    if not contact:
        return "No emergency contact is set."

    # For now, simulate alert
    # Later this connects to SMS/email API
    return f"Emergency alert would be sent to {contact}."
