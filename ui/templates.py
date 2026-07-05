"""All message templates."""
from config.config import DEFAULT_SESSION_RATE_ETB, PLATFORM_COMMISSION_ETB, TUTOR_NET_RATE_ETB

DIVIDER = "─" * 26

def _sec(title): return f"\n{DIVIDER}\n*{title}*\n{DIVIDER}"


# ── Unregistered ──────────────────────────────────────────────────────────────

def welcome_unregistered(first_name: str) -> str:
    return (
        f"👋 Hello, *{first_name}!*\n\n"
        f"Welcome to *Akew Tutor* — your online tutoring platform.\n\n"
        f"{_sec('Get Started')}\n\n"
        f"Are you a *Student* looking to learn,\nor a *Tutor* ready to teach?\n\n"
        f"👇 Choose your role below:"
    )

def about_message() -> str:
    return (
        f"ℹ️ *About Akew Tutor*\n\n"
        f"Connecting students with qualified tutors across Ethiopia.\n"
        f"{_sec('What We Offer')}\n\n"
        f"  🎓  One-on-one tutoring via Zoom\n"
        f"  📹  Recorded sessions for review\n"
        f"  📆  Flexible weekly schedules\n"
        f"  ✅  Verified tutors only\n"
        f"  💰  Transparent payments\n"
        f"  🚨  24/7 admin support\n"
        f"{_sec('Rates')}\n\n"
        f"  💵  Student rate: *{DEFAULT_SESSION_RATE_ETB:.0f} ETB/hr*\n"
        f"  💸  Tutor earns: *{TUTOR_NET_RATE_ETB:.0f} ETB/hr* (platform fee: {PLATFORM_COMMISSION_ETB:.0f} ETB/session)"
    )

# ── Student ───────────────────────────────────────────────────────────────────

def student_dashboard(full_name, user_id, upcoming, payment_status,
                      amount_due, rate) -> str:
    pay_icon = "✅" if payment_status == "paid" else "⚠️"
    pay_text = "Paid ✓" if payment_status == "paid" else f"*{amount_due:.0f} ETB* due"
    lines = [
        f"🎓 *Welcome back, {full_name.split()[0]}!*\n",
        _sec("Dashboard"),
        f"\n🆔  `{user_id}`",
        f"💳  Payment: {pay_icon} {pay_text}",
        f"💵  Your rate: *{rate:.0f} ETB / hr*",
        _sec("Upcoming Sessions"),
    ]
    if upcoming:
        for s in upcoming[:3]:
            dot = "🟢" if s["status"] == "zoom_ready" else "🔵"
            lines.append(
                f"\n{dot} *{s['subject']}*\n"
                f"    👨‍🏫 {s['tutor_name']}\n"
                f"    🕐 {s['start']} – {s['end']}\n"
                f"    📋 `{s['session_id']}`"
            )
        if len(upcoming) > 3:
            lines.append(f"\n    _+ {len(upcoming)-3} more_")
    else:
        lines.append("\n_No upcoming sessions yet._")
    lines.append(f"\n{DIVIDER}")
    return "\n".join(lines)

def student_sessions(upcoming, past) -> str:
    lines = [f"📅 *Your Sessions*\n"]
    if upcoming:
        lines.append(_sec("Upcoming"))
        for s in upcoming:
            zoom = f"\n    🔗 [Join Zoom]({s['zoom_link']})" if s.get("zoom_link") else ""
            lines.append(
                f"\n🔵 *{s['subject']}*  `{s['session_id']}`\n"
                f"    👨‍🏫 {s['tutor_name']}\n"
                f"    🕐 {s['start']} – {s['end']}{zoom}"
            )
    else:
        lines.append("\n_No upcoming sessions._")
    if past:
        lines.append(_sec("Recent Past"))
        for s in past[:5]:
            icon = "✅" if s["status"] == "completed" else "❌"
            lines.append(
                f"\n{icon} *{s['subject']}*  `{s['session_id']}`\n"
                f"    🕐 {s['start']}  ·  _{s['status']}_"
            )
    return "\n".join(lines)

def student_schedule(schedules) -> str:
    lines = [f"📆 *Your Weekly Schedule*\n"]
    if not schedules:
        lines.append("_No schedules assigned yet._\nContact your admin.")
        return "\n".join(lines)
    for s in schedules:
        lines.append(
            f"\n📚 *{s['subject']}*\n"
            f"    👨‍🏫 {s['tutor_name']}\n"
            f"    📅 {s['days']}\n"
            f"    🕐 {s['time']}\n"
            f"    🆔 `{s['schedule_id']}`"
        )
    return "\n".join(lines)

def student_payments(rate, payments) -> str:
    lines = [f"💳 *Your Payments*\n", f"💵 Rate: *{rate:.0f} ETB / hr*\n"]
    if not payments:
        lines.append("_No payment records yet._")
        return "\n".join(lines)
    for p in payments:
        icon = "✅" if p["status"] == "completed" else ("⏳" if p["status"] == "screenshot_uploaded" else "❌")
        lines.append(
            f"{icon} *{p['month']}*  ·  {p['amount']:.0f} ETB  ·  _{p['status'].replace('_',' ')}_\n"
            f"    `{p['transaction_id']}`\n"
        )
    return "\n".join(lines)

# ── Tutor ─────────────────────────────────────────────────────────────────────

def tutor_dashboard(full_name, user_id, upcoming_count,
                    total_earned, is_verified) -> str:
    status = "✅ Verified" if is_verified else "⏳ Pending approval"
    return "\n".join([
        f"👨‍🏫 *Welcome back, {full_name.split()[0]}!*\n",
        _sec("Dashboard"),
        f"\n🆔  `{user_id}`",
        f"📋  Status: {status}",
        f"📅  Upcoming sessions: *{upcoming_count}*",
        f"💰  Total earned: *{total_earned:.0f} ETB*",
        f"\n{DIVIDER}",
    ])

def tutor_sessions(upcoming, past) -> str:
    lines = [f"📅 *Your Sessions*\n"]
    if upcoming:
        lines.append(_sec("Upcoming"))
        for s in upcoming:
            zoom = (f"\n    🔗 [Zoom Link]({s['zoom_link']})" if s.get("zoom_link")
                    else f"\n    ⚠️ No Zoom link yet — tap 📹 on your dashboard")
            lines.append(
                f"\n🔵 *{s['subject']}*  `{s['session_id']}`\n"
                f"    👤 {s['student_name']}\n"
                f"    🕐 {s['start']} – {s['end']}{zoom}"
            )
    else:
        lines.append("\n_No upcoming sessions._")
    if past:
        lines.append(_sec("Recent Past"))
        for s in past[:5]:
            icon = "✅" if s["status"] == "completed" else "❌"
            lines.append(
                f"\n{icon} *{s['subject']}*  `{s['session_id']}`\n"
                f"    👤 {s['student_name']}  ·  {s['start']}"
            )
    return "\n".join(lines)

def tutor_earnings(total_earned, payouts) -> str:
    lines = [f"💰 *Your Earnings*\n", f"💵 *Total paid out: {total_earned:.0f} ETB*\n", _sec("History")]
    if not payouts:
        lines.append("\n_No payout records yet._")
        return "\n".join(lines)
    for p in payouts:
        icon = "✅" if p["status"] == "paid" else "⏳"
        lines.append(
            f"\n{icon} *{p['month']}*\n"
            f"    Sessions: {p['sessions']}  ·  Net: *{p['net']:.0f} ETB*  ·  _{p['status']}_"
        )
    return "\n".join(lines)

def tutor_schedule(schedules) -> str:
    lines = [f"📆 *Your Teaching Schedule*\n"]
    if not schedules:
        lines.append("_No schedules assigned yet._")
        return "\n".join(lines)
    for s in schedules:
        lines.append(
            f"\n📚 *{s['subject']}*\n"
            f"    👤 {s['student_name']}\n"
            f"    📅 {s['days']}\n"
            f"    🕐 {s['time']}\n"
            f"    🆔 `{s['schedule_id']}`"
        )
    return "\n".join(lines)

# ── Admin ─────────────────────────────────────────────────────────────────────

def admin_dashboard(full_name, user_id, stats) -> str:
    attention = []
    if stats.get("pending_tutors", 0) > 0:
        attention.append(f"  ⏳  {stats['pending_tutors']} tutor(s) pending approval")
    if stats.get("unpaid_students", 0) > 0:
        attention.append(f"  ❌  {stats['unpaid_students']} student(s) haven't paid")
    if stats.get("open_emergencies", 0) > 0:
        attention.append(f"  🚨  {stats['open_emergencies']} open emergency/ies")
    if stats.get("open_issues", 0) > 0:
        attention.append(f"  ⚠️  {stats['open_issues']} open issue(s)")
    if stats.get("students_no_tutor", 0) > 0:
        attention.append(f"  👤  {stats['students_no_tutor']} student(s) need a tutor")

    lines = [f"👑 *Welcome, {full_name.split()[0]}!*\n"]

    if attention:
        lines.append(_sec("Needs Attention"))
        lines.append("\n" + "\n".join(attention))
    else:
        lines.append(_sec("Needs Attention"))
        lines.append("\n  ✅  Everything looks good!")

    lines.append(_sec("Overview"))
    lines.append(
        f"\n👥  Students: *{stats['students']}*  ·  Tutors: *{stats['verified_tutors']}*\n"
        f"📅  Sessions completed: *{stats['completed_sessions']}*\n"
        f"💰  Platform revenue: *{stats['platform_revenue']:.0f} ETB*"
    )
    lines.append(f"\n{DIVIDER}")
    return "\n".join(lines)

def admin_emergencies(items) -> str:
    if not items:
        return "✅ *No open emergencies.*\n\nAll clear!"
    lines = [f"🚨 *Open Emergencies ({len(items)})*\n"]
    for e in items:
        lines.append(
            f"\n🔴 `{e['emergency_id']}`\n"
            f"    By: {e['reporter']} (`{e['reporter_id']}`)\n"
            f"    Type: {e['issue_type']}\n"
            f"    {e['description']}\n"
            f"    🕐 {e['created_at']}"
            + (f"\n    🔒 Claimed by: {e['claimed_by']}" if e.get("claimed_by") else "")
        )
    return "\n".join(lines)

def admin_issues(items) -> str:
    if not items:
        return "✅ *No open issues.*\n\nAll clear!"
    lines = [f"⚠️ *Open Issues ({len(items)})*\n"]
    for e in items:
        lines.append(
            f"\n🟡 `{e['emergency_id']}`\n"
            f"    By: {e['reporter']} (`{e['reporter_id']}`)\n"
            f"    {e['description']}\n"
            f"    🕐 {e['created_at']}"
            + (f"\n    🔒 Claimed by: {e['claimed_by']}" if e.get("claimed_by") else "")
        )
    return "\n".join(lines)

def admin_user_audit(data) -> str:
    u = data["user"]
    lines = [
        f"🔍 *User Audit: {u['full_name']}*\n",
        _sec("Profile"),
        f"\n🆔  `{u['user_id']}`",
        f"📱  {u['phone']}",
        f"🎭  {u['role'].capitalize()}",
        f"✅  Verified: {'Yes' if u['is_verified'] else 'No'}",
        f"⚡  {'Active' if u['is_active'] else '🚫 Suspended'}",
        f"📅  Joined: {u['created_at']}",
    ]
    if data["sessions"]:
        lines.append(_sec(f"Sessions ({len(data['sessions'])})"))
        for s in data["sessions"][:5]:
            lines.append(f"\n  • `{s['session_id']}` {s['subject']} — {s['date']} — _{s['status']}_")
    if data["emergencies"]:
        lines.append(_sec(f"Issues ({len(data['emergencies'])})"))
        for e in data["emergencies"]:
            lines.append(f"\n  • `{e['emergency_id']}` {e['issue_type']} — _{e['status']}_")
    return "\n".join(lines)

# ── Registration ──────────────────────────────────────────────────────────────

def reg_step(role, step, total, prompt, tip=None) -> str:
    bar = "●" * step + "○" * (total - step)
    icon = "🎓" if role == "student" else "👨‍🏫"
    lines = [
        f"{icon} *{role.capitalize()} Registration*\n",
        f"`{bar}`  Step {step} of {total}\n",
        f"{DIVIDER}\n",
        prompt,
    ]
    if tip:
        lines.append(f"\n💡 _{tip}_")
    return "\n".join(lines)

def reg_complete_student(full_name, user_id) -> str:
    return (
        f"🎉 *Registration Complete!*\n\n"
        f"Welcome to Akew Tutor, *{full_name.split()[0]}*!\n"
        f"{_sec('Your Account')}\n\n"
        f"🆔  Student ID: `{user_id}`\n\n"
        f"Please complete your first payment to unlock your dashboard."
    )

def reg_complete_tutor(full_name, user_id) -> str:
    return (
        f"🎉 *Application Submitted!*\n\n"
        f"Thank you, *{full_name.split()[0]}*!\n"
        f"{_sec('Your Account')}\n\n"
        f"🆔  Tutor ID: `{user_id}`\n\n"
        f"⏳ Your documents are under review.\n"
        f"You'll be notified once approved."
    )

# ── Notifications ─────────────────────────────────────────────────────────────

def payment_confirmed_student(full_name, month, amount) -> str:
    return (
        f"✅ *Payment Confirmed!*\n\n"
        f"Hi {full_name.split()[0]}, your payment of *{amount:.0f} ETB* "
        f"for *{month}* has been confirmed.\n\n"
        f"Your dashboard is now unlocked."
    )

def payout_paid_tutor(full_name, month, net) -> str:
    return (
        f"💸 *Payout Processed!*\n\n"
        f"Hi {full_name.split()[0]}, your payout of *{net:.0f} ETB* "
        f"for *{month}* has been paid. 🎉"
    )
