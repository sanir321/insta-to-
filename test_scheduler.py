from datetime import datetime, timedelta

def calculate_wait(now, target_time_str):
    target_h, target_m = map(int, target_time_str.split(':'))
    target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    
    wait_seconds = (target - now).total_seconds()
    return target, wait_seconds

def test_scheduling():
    print("[INFO] Testing Scheduler Logic...")
    
    # Case 1: Currently 8 PM, Target 2 AM (Today 2 AM is past, should be tomorrow)
    now1 = datetime(2026, 4, 1, 20, 0, 0)
    target1, wait1 = calculate_wait(now1, "02:00")
    print(f"Test 1 (Evening): Now: {now1} -> Next Run: {target1} (Wait: {wait1/3600:.1f}h)")
    assert target1 == datetime(2026, 4, 2, 2, 0, 0)
    assert wait1 == 6 * 3600 # 8pm to 2am is 6 hours
    
    # Case 2: Currently 1 AM, Target 2 AM (Before 2 AM, should be today)
    now2 = datetime(2026, 4, 1, 1, 0, 0)
    target2, wait2 = calculate_wait(now2, "02:00")
    print(f"Test 2 (Early Morning): Now: {now2} -> Next Run: {target2} (Wait: {wait2/3600:.1f}h)")
    assert target2 == datetime(2026, 4, 1, 2, 0, 0)
    assert wait2 == 1 * 3600 # 1am to 2am is 1 hour

    # Case 3: Currently Exactly 2 AM
    now3 = datetime(2026, 4, 1, 2, 0, 0)
    target3, wait3 = calculate_wait(now3, "02:00")
    print(f"Test 3 (Exactly 2 AM): Now: {now3} -> Next Run: {target3} (Wait: {wait3/3600:.1f}h)")
    assert target3 == datetime(2026, 4, 2, 2, 0, 0)
    assert wait3 == 24 * 3600
    
    print("\n[SUCCESS] Scheduler logic verified successfully!")

if __name__ == "__main__":
    test_scheduling()
