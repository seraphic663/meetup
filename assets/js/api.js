export class ApiError extends Error {
  constructor(message, { status = 500, code = 'unknown_error', details = null, requestId = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

function extractError(payload, status) {
  const error = payload?.error;
  if (error && typeof error === 'object') {
    return new ApiError(
      error.message || '请求失败',
      {
        status,
        code: error.code || 'request_failed',
        details: error.details || null,
        requestId: payload?.request_id || null,
      },
    );
  }
  if (typeof error === 'string') {
    return new ApiError(error, {
      status,
      code: error,
      details: payload?.details || null,
      requestId: payload?.request_id || null,
    });
  }
  return new ApiError('请求失败，请稍后重试', {
    status,
    code: 'request_failed',
    requestId: payload?.request_id || null,
  });
}

export async function requestJson(url, { method = 'GET', body = null } = {}) {
  const options = { method, headers: {} };
  if (body) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new ApiError('网络请求失败，请检查连接后重试', { status: 0, code: 'network_error' });
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    payload = null;
  }

  if (!response.ok) {
    throw extractError(payload, response.status);
  }
  return payload;
}
