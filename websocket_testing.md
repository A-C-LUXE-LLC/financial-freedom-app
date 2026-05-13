# WebSocket Integration Test Suite (Socket.IO over /api/socket.io)

## Test Coverage Requirements

### 1. Connection Lifecycle Testing
- Test successful connection to `/api/socket.io`
- Test connection failure with wrong path (should fail)
- Test disconnect event fires correctly
- Test connection status tracking
- Verify resource cleanup on disconnect

### 2. Room Management Testing
- Test `join_room` event with `room_id="demo_session"`
- Test `join_room` with missing room_id (should handle gracefully)
- Test multiple clients in same room
- Test clients in different rooms (messages isolated)

### 3. Broadcasting & Real-time Sync Testing
- Test `state_update` event received by all clients in same room after buy/approve/fund
- Test `price_tick` event broadcast every ~2s reaches all clients
- Test approval flow: kid creates pending trade -> parent client receives `pending_added` -> parent approves -> kid client receives `trade_approved` + confetti trigger

### 4. Error Handling Testing
- Test malformed room_id handling
- Test missing data in events
- Test rapid connect/disconnect cycles
- Test reconnection logic

### 5. Multi-user Collaboration Testing
- Test 2 clients (parent tab + kid tab) in same `demo_session` room receive each other's updates
- Test no data loss on rapid concurrent updates

### 6. Performance Testing
- Test rapid successive price ticks (no message loss)

## Backend Implementation Requirements
- Use `python-socketio` client library (NOT requests)
- Test actual Socket.IO events (`connect`, `disconnect`, `join_room`, `state_update`, `price_tick`, `pending_added`, `trade_approved`)
- Generate test report showing pass/fail for each category
