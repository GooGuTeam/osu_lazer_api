# Mark as Read API Implementation

基于 osu! lazer 源代码实现的聊天频道标记为已读 API

## API 端点

```
PUT /api/v2/chat/channels/{channel_id}/mark-as-read/{message_id}
```

## 功能描述

将指定聊天频道标记为已读到指定消息。这个 API 完全基于 osu! lazer 客户端的期望实现。

## 参数

- `channel_id` (int): 频道 ID
- `message_id` (int): 最后已读消息的 ID

## 请求方法

- **Method**: PUT
- **Content-Type**: application/json
- **Authorization**: Bearer token required

## 响应

### 成功响应 (200 OK)
```json
{}
```

### 错误响应

#### 404 Not Found - 频道不存在
```json
{
  "detail": "Channel not found"
}
```

#### 404 Not Found - 消息不存在
```json
{
  "detail": "Message not found in this channel"
}
```

#### 403 Forbidden - 权限不足
```json
{
  "detail": "Insufficient privileges to access this channel"
}
```

#### 403 Forbidden - 未加入频道
```json
{
  "detail": "You must join the channel first"
}
```

## 实现细节

### 数据库结构

实现基于以下数据库表：

1. **channels** - 频道信息
2. **channel_users** - 用户频道关系，包含 `last_read_message_id` 字段
3. **chat_messages** - 聊天消息

### 验证逻辑

1. **频道存在性验证**: 检查频道是否存在
2. **权限验证**: 检查用户是否有访问该频道的权限
3. **成员关系验证**: 检查用户是否已加入该频道
4. **消息验证**: 检查指定的消息是否存在于该频道中
5. **更新操作**: 更新用户在该频道的 `last_read_message_id`

### osu! 源代码对应关系

此实现完全基于 osu! lazer 源代码：

- **请求类**: `MarkChannelAsReadRequest.cs`
  ```csharp
  protected override string Target => $"chat/channels/{Channel.Id}/mark-as-read/{Message.Id}";
  protected override WebRequest CreateWebRequest()
  {
      var req = base.CreateWebRequest();
      req.Method = HttpMethod.Put;
      return req;
  }
  ```

- **频道管理**: `ChannelManager.cs`
  ```csharp
  public void MarkChannelAsRead(Channel channel)
  {
      if (channel.LastMessageId == channel.LastReadId)
          return;

      var message = channel.Messages.FindLast(msg => !(msg is LocalMessage));
      if (message == null)
          return;

      var req = new MarkChannelAsReadRequest(channel, message);
      req.Success += () => channel.LastReadId = message.Id;
      // ...
  }
  ```

## 使用示例

### 使用 curl

```bash
curl -X PUT \
  "http://localhost:8000/api/v2/chat/channels/1/mark-as-read/123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### 使用 Python requests

```python
import requests

headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

response = requests.put(
    "http://localhost:8000/api/v2/chat/channels/1/mark-as-read/123",
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
```

## 相关 API

- `GET /api/v2/chat/channels` - 获取频道列表（现在包含 `last_read_id` 和 `last_message_id`）
- `GET /api/v2/chat/channels/{channel_id}/messages` - 获取频道消息
- `PUT /api/v2/chat/channels/{channel_id}/users/{user_id}` - 加入频道

## 测试

使用提供的测试脚本 `test_mark_as_read.py` 来验证实现：

```bash
python test_mark_as_read.py
```

测试脚本会：
1. 获取认证令牌
2. 获取可用频道
3. 加入测试频道
4. 发送/获取消息
5. 测试标记为已读功能
6. 验证更新结果
7. 测试错误情况

## 数据流

1. **osu! 客户端** → `PUT /chat/channels/{id}/mark-as-read/{msg_id}`
2. **API 服务器** → 验证权限和数据有效性
3. **数据库** → 更新 `channel_users.last_read_message_id`
4. **API 服务器** → 返回成功响应
5. **osu! 客户端** → 更新本地频道状态

## 注意事项

1. API 完全遵循 osu! lazer 源代码的实现模式
2. 错误处理与官方实现保持一致
3. 数据库设计支持多用户并发操作
4. 所有操作都有适当的权限验证
5. 响应格式与 osu! 客户端期望完全匹配 
