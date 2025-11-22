# Proxy Mode Visibility and Reliability Enhancements

## Overview
This update addresses the issue where proxy usage was not clearly visible during account detection, causing confusion about whether proxies were actually being used.

## Problem Statement
- After enabling proxies, detection results often showed "本地连接" (local connection)
- No clear indication of which proxy (host:port/type) was used
- Proxy failures fell back to local silently without user notification
- No visibility into failure reasons or retry attempts

## Solution Implemented

### 1. Proxy Usage Tracking (`ProxyUsageRecord`)
A new dataclass tracks detailed information about each proxy attempt:
- Account name
- Proxy attempted (type, host, port)
- Attempt result (success/failure reason)
- Whether fallback to local occurred
- Error details
- Whether it's a residential proxy
- Time elapsed

### 2. Enhanced Configuration Options
New environment variables in `.env`:

```bash
# Number of different proxies to try before falling back to local
PROXY_ROTATE_RETRIES=2

# Show detailed failure reasons (timeout, dns_error, auth_failed, etc.)
PROXY_SHOW_FAILURE_REASON=true

# Maximum number of proxy usage records to keep in memory
PROXY_USAGE_LOG_LIMIT=500

# Enable verbose debug logging for proxy attempts
PROXY_DEBUG_VERBOSE=false
```

### 3. Proxy Rotation Logic
When a proxy fails, the system now:
1. Tries up to N different proxies (configured by `PROXY_ROTATE_RETRIES`)
2. Records each attempt with detailed error classification
3. Only falls back to local after all proxy attempts fail
4. Clearly indicates in the result string whether proxy or local was used

### 4. Enhanced Result Strings
Detection results now show detailed connection information:

**Success with proxy:**
```
ID:12345 | SOCKS5 203.0.113.5:1080 | Good news, no limits...
```

**With debug mode enabled:**
```
ID:12345 | SOCKS5 203.0.113.5:1080 (ok 1.24s) | Good news, no limits...
```

**Failure with reason:**
```
ID:12345 | HTTP 192.168.1.1:8080 | timeout
```

**Local fallback:**
```
ID:12345 | 本地连接 | Good news, no limits...
```

### 5. Real-Time Statistics Display
During batch processing, the progress message now shows:

```
📡 代理使用统计
• 已使用代理: 45
• 回退本地: 3
• 失败代理: 2
```

### 6. Improved Error Classification
Proxy failures are now categorized as:
- `timeout` - Connection timed out
- `connection_refused` - Connection refused by proxy
- `auth_failed` - Authentication failed
- `dns_error` - DNS resolution failed
- `network_error` - Generic network error

### 7. Debug Mode
When `PROXY_DEBUG_VERBOSE=true`, detailed console output shows:
```
[#1] 使用代理 socks5 203.0.113.5:1080 检测账号 8613.session
Connect failed: timeout (1.99s)
Retrying with next proxy...
[#2] 使用代理 http 192.168.1.1:8080 检测账号 8613.session
✅ 连接成功
```

## Technical Implementation

### Modified Classes

#### `Config`
- Added 4 new configuration variables
- Updated `.env` template generation

#### `ProxyManager`
- Added `get_proxy_activation_detail()` method for diagnostic visibility
- Returns detailed status of proxy mode activation

#### `SpamBotChecker`
- Refactored `check_account_status()` to implement proxy rotation
- Created new `_single_check_with_proxy()` method for cleaner separation
- Added `proxy_usage_records` deque for tracking (limited to configured size)
- Added `get_proxy_usage_stats()` for aggregating statistics

#### `EnhancedBot`
- Updated progress callback to display proxy usage statistics
- Enhanced final results display with detailed proxy metrics

## Backward Compatibility
All new configuration variables have sensible defaults:
- `PROXY_ROTATE_RETRIES=2` - Try 2 different proxies
- `PROXY_SHOW_FAILURE_REASON=true` - Show failure reasons
- `PROXY_USAGE_LOG_LIMIT=500` - Keep last 500 records
- `PROXY_DEBUG_VERBOSE=false` - Debug mode off by default

Existing functionality is preserved when these variables are not set.

## Usage Examples

### Enable Detailed Proxy Visibility
```bash
# In .env file
PROXY_ROTATE_RETRIES=3
PROXY_SHOW_FAILURE_REASON=true
PROXY_DEBUG_VERBOSE=true
```

### Monitor Proxy Usage
Check the progress messages during batch detection to see:
- How many accounts used proxies successfully
- How many fell back to local connection
- How many proxy attempts failed

### Troubleshoot Proxy Issues
1. Enable `PROXY_DEBUG_VERBOSE=true`
2. Watch console output for detailed connection attempts
3. Check result strings for specific failure reasons
4. Review the proxy statistics in final results

## Performance Impact
- Minimal overhead: Only tracking metadata, not full logs
- Deque with size limit prevents memory growth
- Statistics calculated on-demand
- No impact when proxy mode is disabled

## Future Enhancements (Not Implemented)
- Export proxy usage log as CSV
- Real-time failed proxy quarantine list
- Per-proxy success rate tracking
- Automatic proxy health scoring

## Testing
- ✅ Python syntax validation passed
- ✅ Core dataclass and logic tested
- ✅ Statistics calculation verified
- ✅ Security scan (CodeQL) passed with 0 alerts
- ✅ Backward compatibility confirmed (all defaults work)

## Migration Guide
No migration needed. Simply update to the latest version and optionally configure the new environment variables in your `.env` file.

## Support
For issues or questions, please refer to the repository's issue tracker.
