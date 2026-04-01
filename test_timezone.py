import pytz
from datetime import datetime, timedelta

def calculate_wait(now_dt, target_time_str):
    target_h, target_m = map(int, target_time_str.split(':'))
    target = now_dt.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
    if target <= now_dt:
        target += timedelta(days=1)
    
    wait_seconds = (target - now_dt).total_seconds()
    return target, wait_seconds

def test_timezone_scheduling():
    print("[INFO] Testing Timezone-Aware Scheduler Logic...")
    
    # Target 2:00 AM
    target_time = "02:00"
    
    # Case 1: Indian Standard Time (IST) - Now is 8 PM (20:00)
    tz_ist = pytz.timezone("Asia/Kolkata")
    now_ist = tz_ist.localize(datetime(2026, 4, 1, 20, 0, 0))
    target1, wait1 = calculate_wait(now_ist, target_time)
    print(f"Test 1 (IST Evening): Now: {now_ist} -> Next Run: {target1} (Wait: {wait1/3600:.1f}h)")
    assert wait1 == 6 * 3600
    
    # Case 2: New York Time (EST) - Now is 11 PM (23:00)
    tz_est = pytz.timezone("America/New_York")
    now_est = tz_est.localize(datetime(2026, 4, 1, 23, 0, 0))
    target2, wait2 = calculate_wait(now_est, target_time)
    print(f"Test 2 (EST Night): Now: {now_est} -> Next Run: {target2} (Wait: {wait2/3600:.1f}h)")
    assert wait2 == 3 * 3600

    # Case 3: UTC Time (Railway Default) - Now is 10 PM (22:00)
    tz_utc = pytz.utc
    now_utc = tz_utc.localize(datetime(2026, 4, 1, 22, 0, 0))
    target3, wait3 = calculate_wait(now_utc, target_time)
    print(f"Test 3 (UTC Night): Now: {now_utc} -> Next Run: {target3} (Wait: {wait3/3600:.1f}h)")
    assert wait3 == 4 * 3600
    
    print("\n[SUCCESS] Timezone-aware scheduler logic verified successfully!")

if __name__ == "__main__":
    test_timezone_scheduling()
