from datetime import datetime, timedelta
from database import (
    add_activity,
    get_flag,
    get_activities_for_day as db_get_activities_for_day,
    activity_applies_to_day as db_activity_applies_to_day,
    get_conflicting_activities
)
PHYSICAL_CATEGORIES = ["Cvičení", "Sport", "Procházka", "Fyzická práce"]


def _ensure_load_type(activity):
    if len(activity) < 13:
        return tuple(list(activity) + ["mental"])
    return activity


def _pad_activity(activity, length, fill=None):
    if len(activity) >= length:
        return activity
    return tuple(list(activity) + [fill] * (length - len(activity)))


def _is_all_day_time(sh, sm, eh, em):
    return sh == 0 and sm == 0 and eh == 23 and em == 59


def activity_applies_to_day(activity, date_str):
    activity_id = activity[0] if activity else None
    if not activity_id:
        return False
    return db_activity_applies_to_day(activity_id, date_str)


def get_activities_for_day(date_str):
    return db_get_activities_for_day(date_str)


def add_activity_to_multiple_days(name, category, sh, sm, eh, em, difficulty, dates, load_type='mental'):
    """Přidá aktivitu na více dní najednou"""
    for date_str in dates:
        add_activity(
            name=name,
            category=category,
            sh=sh,
            sm=sm,
            eh=eh,
            em=em,
            difficulty=difficulty,
            date=date_str,
            recurring=0,
            recurring_days=None,
            recurring_date=None,
            load_type=load_type
        )


def get_date_range(start_date_str, end_date_str):
    start = datetime.fromisoformat(start_date_str)
    end = datetime.fromisoformat(end_date_str)
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def is_all_day_activity(activity):
    """Kontroluje, zda je aktivita celodenní"""
    activity = _ensure_load_type(activity)

    return _is_all_day_time(activity[3], activity[4], activity[5], activity[6])


def format_activity_time(activity):
    """Vrátí formátovaný čas aktivity"""
    if len(activity) < 7:
        return "00:00 - 00:00"
    
    # Celodenní aktivita?
    if _is_all_day_time(activity[3], activity[4], activity[5], activity[6]):
        return "Celodenní"
    
    return f"{activity[3]:02d}:{activity[4]:02d} - {activity[5]:02d}:{activity[6]:02d}"


def suggest_after_hours_difficulty(category, start_h, start_m, current_difficulty):
    """Navrhne obtiznost podle casu zacatku aktivity."""
    try:
        difficulty = int(current_difficulty)
    except (TypeError, ValueError):
        difficulty = 1

    difficulty = max(1, min(5, difficulty))

    minutes = (int(start_h) * 60) + int(start_m)
    is_physical = category in PHYSICAL_CATEGORIES

    # Late evening or very early activities should be gentler.
    if minutes >= 20 * 60 or minutes < 6 * 60:
        delta = 2 if is_physical and minutes >= 21 * 60 else 1
        return max(1, difficulty - delta)

    # Slightly reduce physical intensity in the early evening.
    if minutes >= 18 * 60 and is_physical:
        return max(1, difficulty - 1)

    return difficulty


def calculate_daily_load(date_str):
    """Vrátí (physical_load, mental_load) - aktivita má svou náročnost + samostatnou hodnotu odpočinku"""
    activities = get_activities_for_day(date_str)
    all_day_minutes = int(get_flag("all_day_minutes", "480"))
    physical = 0.0
    mental = 0.0

    for act in activities:
        act = _ensure_load_type(act)
        
        difficulty = int(act[7]) if act[7] is not None else 1
        is_rest = act[14] if len(act) > 14 else 0
        rest_type = act[15] if len(act) > 15 and act[15] else None
        rest_amount = act[16] if len(act) > 16 and act[16] else 0
        
        if is_all_day_activity(act):
            minutes = all_day_minutes
        else:
            start = act[3] * 60 + act[4]
            end = act[5] * 60 + act[6]
            minutes = max(0, end - start)
        
        # 1. Přidej základní náročnost aktivity podle jejího typu
        category = act[2] if act[2] else ""
        load_type = act[12] if len(act) > 12 and act[12] else None
        
        if not load_type:
            load_type = 'physical' if category in PHYSICAL_CATEGORIES else 'mental'
        
        load_value = (minutes / 60.0) * difficulty
        
        if load_type == 'physical':
            physical += load_value
        else:
            mental += load_value
        
        # 2. Pokud má aktivita odpočinek, odečti samostatnou hodnotu odpočinku
        if is_rest and rest_amount > 0:
            rest_load = (minutes / 60.0) * rest_amount
            
            if rest_type == "physical":
                physical -= rest_load
            elif rest_type == "mental":
                mental -= rest_load

    return round(max(0, physical), 2), round(max(0, mental), 2)


def get_daily_recommendation(date_str):
    """Doporučení podle fyzické a psychické zátěže + nastavení"""
    physical, mental = calculate_daily_load(date_str)
    
    target_physical_min = float(get_flag("target_physical_min", "3"))
    target_physical_max = float(get_flag("target_physical_max", "6"))
    target_mental_min = float(get_flag("target_mental_min", "4"))
    target_mental_max = float(get_flag("target_mental_max", "8"))
    
    balance_mode = get_flag("balance_mode", "rest")  # 'rest' nebo 'balance'
    
    messages = []
    total_status = "balanced"
    
    # Kontrola fyzické zátěže
    if physical < target_physical_min:
        messages.append(f"🔴 Fyzická zátěž {physical} < cíl ({target_physical_min}–{target_physical_max})")
        total_status = "low"
    elif physical > target_physical_max:
        messages.append(f"🔴 Fyzická zátěž {physical} > cíl ({target_physical_min}–{target_physical_max})")
        total_status = "high"
    else:
        messages.append(f"🟢 Fyzická zátěž {physical} ✓ ({target_physical_min}–{target_physical_max})")
    
    # Kontrola psychické zátěže
    if mental < target_mental_min:
        messages.append(f"🔴 Psychická zátěž {mental} < cíl ({target_mental_min}–{target_mental_max})")
        if total_status == "balanced":
            total_status = "low"
    elif mental > target_mental_max:
        messages.append(f"🔴 Psychická zátěž {mental} > cíl ({target_mental_min}–{target_mental_max})")
        if total_status == "balanced":
            total_status = "high"
    else:
        messages.append(f"🟢 Psychická zátěž {mental} ✓ ({target_mental_min}–{target_mental_max})")
    
    # Doporučení podle režimu
    if total_status == "high":
        if balance_mode == "balance":
            # Vyrovnat druhou náročností
            if physical > target_physical_max and mental < target_mental_max:
                title = "Vyrovnat aktivní odpočinek"
                text = "Vysoká fyzická zátěž → přidejte psychickou aktivitu (čtení, učení).\n" + "\n".join(messages)
            elif mental > target_mental_max and physical < target_physical_max:
                title = "Vyrovnat aktivní odpočinek"
                text = "Vysoká psychická zátěž → přidejte fyzickou aktivitu (cvičení, procházku).\n" + "\n".join(messages)
            else:
                title = "Doporučený odpočinek"
                text = "Obě zátěže vysoké → zkuste přesunout některé aktivity.\n" + "\n".join(messages)
        else:
            title = "Doporučený odpočinek"
            text = "Zátěž je vysoká → zkuste přesunout některé aktivity.\n" + "\n".join(messages)
    
    elif total_status == "low":
        title = "Zvyšte aktivitu"
        if physical < target_physical_min and mental < target_mental_min:
            text = "Obě zátěže pod cílem → přidejte aktivity.\n" + "\n".join(messages)
        elif physical < target_physical_min:
            text = "Nízká fyzická zátěž → přidejte cvičení nebo pohyb.\n" + "\n".join(messages)
        else:
            text = "Nízká psychická zátěž → přidejte studium nebo práci.\n" + "\n".join(messages)
    
    else:
        title = "Vyváženo"
        text = "\n".join(messages)
    
    return title, text


def check_conflicts(new_activity, existing_activities, date_str):
    return get_conflicting_activities(
        date_str,
        new_activity["sh"],
        new_activity["sm"],
        new_activity["eh"],
        new_activity["em"]
    )


def find_first_free_slot(activity_dict, existing_activities, date_str, start_search_time=None):
    """Najdi první volný čas pro aktivitu bez konfliktu"""
    if start_search_time is None:
        start_search_time = activity_dict["sh"] * 60 + activity_dict["sm"]
    
    duration = (activity_dict["eh"] - activity_dict["sh"]) * 60 + (activity_dict["em"] - activity_dict["sm"])
    
    current_start = start_search_time
    max_attempts = 100  # Aby se neběželo nekonečně
    
    for _ in range(max_attempts):
        current_end = current_start + duration
        
        # Překročilo by konec dne?
        if current_end > 1439:
            return None  # Nelze umístit
        
        # Kontrola všech aktivit
        test_activity = {
            "sh": current_start // 60,
            "sm": current_start % 60,
            "eh": current_end // 60,
            "em": current_end % 60
        }
        
        if not check_conflicts(test_activity, existing_activities, date_str):
            return test_activity  # Našli jsme volný slot
        
        # Posunout na později (30 minut)
        current_start += 30
    
    return None  # Nelze najít volný čas


def shift_activity_time(activity, new_start_hour, new_start_minute):
    """Posune aktivitu na nový čas, zachová délku trvání"""
    duration = (activity["eh"] - activity["sh"]) * 60 + (activity["em"] - activity["sm"])
    
    new_start_minutes = new_start_hour * 60 + new_start_minute
    new_end_minutes = new_start_minutes + duration
    
    return {
        "sh": new_start_minutes // 60,
        "sm": new_start_minutes % 60,
        "eh": new_end_minutes // 60,
        "em": new_end_minutes % 60
    }
