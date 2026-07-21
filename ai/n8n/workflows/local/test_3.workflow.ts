import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : test_3 - Qwen V3/V4/Level router
// Nodes   : 30  |  Connections: 28
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// WhenChatMessageReceived            chatTrigger
// OpenclawChatReceived               chatTrigger
// RunTestData                        manualTrigger
// TestInputChangeRouteHere           code
// Openclaw                           code
// RouteHelp                          stickyNote
// RouteChatCommandLevelV3V4          code
// IsCloudGpu                         if
// IsLevel                            if
// QwenLevelApi                       httpRequest
// QwenCloudGpuLevelApi               httpRequest
// FormatLevelResponse                code
// FormatCloudGpuLevelResponse        code
// IsV4                               if
// QwenV3Api                          httpRequest
// FormatV3Response                   code
// QwenV4Api                          httpRequest
// FormatV4Response                   code
// IsRag                              if
// IbmSearchApi                       httpRequest
// BuildV4RagPrompt                   code
// QwenV4RagAnswerApi                 httpRequest
// FormatV4RagAnswer                  code
// IsCloudGpuRag                      if
// QwenCloudGpuV4RagApi               httpRequest
// FormatCloudGpuV4RagAnswer          code
// QwenCloudGpuV4Api                  httpRequest
// FormatCloudGpuV4Response           code
// ViewLevelInputLog                  readWriteFile
// ViewLevelOutputLog                 readWriteFile
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// WhenChatMessageReceived
//    → RouteChatCommandLevelV3V4
//      → IsCloudGpu
//        → QwenCloudGpuLevelApi
//          → FormatCloudGpuLevelResponse
//            → IsCloudGpuRag
//              → QwenCloudGpuV4RagApi
//                → FormatCloudGpuV4RagAnswer
//             .out(1) → QwenCloudGpuV4Api
//                → FormatCloudGpuV4Response
//       .out(1) → QwenLevelApi
//          → FormatLevelResponse
//            → IsLevel
//             .out(1) → IsRag
//                → IbmSearchApi
//                  → BuildV4RagPrompt
//                    → QwenV4RagAnswerApi
//                      → FormatV4RagAnswer
//               .out(1) → IsV4
//                  → QwenV4Api
//                    → FormatV4Response
//                 .out(1) → QwenV3Api
//                    → FormatV3Response
//          → ViewLevelInputLog
//          → ViewLevelOutputLog
// OpenclawChatReceived
//    → Openclaw
//      → RouteChatCommandLevelV3V4 (↩ loop)
// RunTestData
//    → TestInputChangeRouteHere
//      → RouteChatCommandLevelV3V4 (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'XtUDQiu8KkvsKpkM',
    name: 'test_3 - Qwen V3/V4/Level router',
    active: true,
    isArchived: false,
    projectId: 'W6XGlfo1EVdrxhD5',
    settings: { executionOrder: 'v1', binaryMode: 'separate', availableInMCP: false },
})
export class Test3QwenV3V4LevelRouterWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: 'b84a8b04-86ec-4a97-a35c-9b733490b97d',
        webhookId: '4dbec87c-b50c-4c47-8202-2bcdb6c57921',
        name: 'When chat message received',
        type: '@n8n/n8n-nodes-langchain.chatTrigger',
        version: 1.4,
        position: [-144, -400],
    })
    WhenChatMessageReceived = {
        options: {},
    };

    @node({
        id: '7c1b2d90-5a16-4c72-8aa0-8c2f6b6a6f11',
        webhookId: 'a5c0c5f2-5c86-4f2b-9d0b-3c4d3a79d2b1',
        name: 'OpenClaw chat received',
        type: '@n8n/n8n-nodes-langchain.chatTrigger',
        version: 1.4,
        position: [-144, -208],
    })
    OpenclawChatReceived = {
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c1',
        name: 'Run test data',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [-144, -32],
    })
    RunTestData = {};

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c2',
        name: 'Test input - change route here',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [128, -32],
    })
    TestInputChangeRouteHere = {
        jsCode: `const route = 'v4_rag';
const device = 'win'; // Change to 'cloud_gpu' to test the Cloud GPU/WebSocket backend.
const prompt = 'Tìm quán ăn ở quận Hai Bà Trưng';
if (!['level', 'v3', 'v4', 'rag', 'v4_rag'].includes(route)) throw new Error('Test route must be level, v3, v4, rag, or v4_rag');
if (!['win', 'cloud_gpu'].includes(device)) throw new Error('Test device must be win or cloud_gpu');
return [{ json: { chatInput: '/' + route + ' ' + prompt, source: 'test', testRoute: route, device } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20e0',
        name: 'OpenClaw',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [128, -208],
    })
    Openclaw = {
        jsCode: `const input = $input.first().json;
const chatInput = String(input.chatInput ?? input.text ?? input.message ?? '').trim();
const sessionId = String(input.sessionId ?? input.session_id ?? input.session?.id ?? '').trim();
const turnId = String(input.turnId ?? input.turn_id ?? input.messageId ?? input.id ?? '').trim() || 'turn-' + Date.now();

const asMessages = (value) => {
    if (Array.isArray(value)) return value;
    if (typeof value === 'string' && value.trim()) return [{ role: 'user', content: value.trim() }];
    return [];
};

const history = asMessages(input.history ?? input.messages);
const normalizedHistory = history
    .map((item) => ({
        role: item?.role === 'assistant' ? 'assistant' : 'user',
        content: String(item?.content ?? item?.text ?? '').trim(),
    }))
    .filter((item) => item.content)
    .slice(-20);

return [{
    json: {
        ...input,
        chatInput,
        sessionId,
        session_id: sessionId,
        turnId,
        turn_id: turnId,
        history: normalizedHistory,
        messages: normalizedHistory,
        openclaw: {
            sessionId,
            turnId,
            transcriptSize: normalizedHistory.length,
        },
    },
}];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20a1',
        name: 'Route help',
        type: 'n8n-nodes-base.stickyNote',
        version: 1,
        position: [384, 144],
    })
    RouteHelp = {
        content: `# CHỌN NHÁNH TRONG Ô CHAT

/level nội dung -> Level
/v3 nội dung    -> V3
/v4 nội dung    -> V4
/v4_rag nội dung -> V4 -> RAG
/gpu_run nội dung -> Cloud GPU

Không có lệnh -> Level tự chọn V3/V4`,
        height: 220,
        width: 320,
        color: 5,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c4',
        name: 'Route chat command (/level /v3 /v4)',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [128, -400],
    })
    RouteChatCommandLevelV3V4 = {
        jsCode: `const input = $input.first().json;
const raw = String(input.chatInput ?? input.text ?? input.message ?? '').trim();
if (!raw) throw new Error('Chat message is empty');

const match = raw.match(/^\\/(gpu_run|v3|v4_rag|v4|level|rag)\\s*/i);
const requestedRoute = match ? match[1].toLowerCase() : '';
const device = requestedRoute === 'gpu_run' || String(input.device ?? 'win').trim().toLowerCase() === 'cloud_gpu' ? 'cloud_gpu' : 'win';
const prompt = (match ? raw.slice(match[0].length) : raw).trim();
if (!prompt) throw new Error('Chat message has no question after the route prefix');

const asMessages = (value) => {
    if (Array.isArray(value)) return value;
    if (typeof value === 'string' && value.trim()) return [{ role: 'user', content: value.trim() }];
    return [];
};
const sourceHistory = asMessages(input.history ?? input.messages);
const samePrompt = (item) => String(item?.content ?? '').trim() === prompt;
const levelHistory = sourceHistory
    .filter((item) => item?.role === 'user' && !samePrompt(item))
    .map((item) => ({ role: 'user', content: String(item.content ?? '').trim() }))
    .filter((item) => item.content)
    .slice(-4);
const modelHistory = sourceHistory
    .filter((item) => (item?.role === 'user' || item?.role === 'assistant') && !(item?.role === 'user' && samePrompt(item)))
    .map((item) => ({ role: item.role, content: String(item.content ?? '').trim() }))
    .filter((item) => item.content)
    .slice(-20);
const systemContext = 'Luôn trả lời ngắn gọn, tự nhiên, bằng tiếng Việt. Bạn là trợ lý trang tuongtac.tv hỗ trợ người dùng tìm dịch vụ, quán, sản phẩm hoặc địa điểm phù hợp quanh họ.';
const levelSystemContext = 'Chỉ trả lời 1 con số từ 1 đến 4, từ list tin nhắn check tin mới nhất là level nào.\\nLevel 1\\nChỉ dùng khi người dùng chỉ chào hỏi, không có câu hỏi, không có nhu cầu.\\n\\nLevel 2\\nKhông liên quan đến tìm kiếm, dịch vụ, quán, sản phẩm hoặc địa điểm.\\n\\nLevel 3\\nđang có nhu cầu liên quan đến tìm kiếm, dịch vụ, quán, sản phẩm hoặc địa điểm, hoặc có đang cần biết thêm.\\n\\nLevel 4\\nKhông rõ.';

return [{ json: {
    ...input,
    requestedRoute,
    device,
    prompt,
    sessionId: input.sessionId ?? input.session_id ?? '',
    levelHistory,
    levelMessages: [
        { role: 'system', content: levelSystemContext },
        ...levelHistory,
        { role: 'user', content: prompt },
    ],
    modelMessages: [
        { role: 'system', content: systemContext },
        ...modelHistory,
        { role: 'user', content: prompt },
    ],
} }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d1',
        name: 'Is Cloud GPU?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [352, -240],
    })
    IsCloudGpu = {
        conditions: {
            options: {
                caseSensitive: false,
                leftValue: '',
                typeValidation: 'strict',
                version: 2.2,
            },
            conditions: [
                {
                    id: 'cloud-gpu-device-condition',
                    leftValue: '={{ $json.device }}',
                    rightValue: 'cloud_gpu',
                    operator: {
                        type: 'string',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b6',
        name: 'Is Level?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [944, 16],
    })
    IsLevel = {
        conditions: {
            options: {
                caseSensitive: false,
                leftValue: '',
                typeValidation: 'strict',
                version: 2.2,
            },
            conditions: [
                {
                    id: 'level-route-condition',
                    leftValue: '={{ $json.requestedRoute === "level" }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b7',
        name: 'Qwen Level API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [592, -48],
    })
    QwenLevelApi = {
        method: 'POST',
        url: 'http://host.docker.internal:8005/openclaw/agent/level',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", system_context: "Chỉ trả lời 1 con số từ 1 đến 4, từ list tin nhắn check tin mới nhất là level nào.\\nLevel 1\\nChỉ dùng khi người dùng chỉ chào hỏi, không có câu hỏi, không có nhu cầu.\\n\\nLevel 2\\nKhông liên quan đến tìm kiếm, dịch vụ, quán, sản phẩm hoặc địa điểm.\\n\\nLevel 3\\nđang có nhu cầu liên quan đến tìm kiếm, dịch vụ, quán, sản phẩm hoặc địa điểm, hoặc có đang cần biết thêm.\\n\\nLevel 4\\nKhông rõ.", user_message: $json.prompt, history: $json.levelHistory, messages: $json.levelMessages, enable_thinking: false, use_lora: false, use_rag: false, temperature: 0.2, top_p: 0.8, max_new_tokens: 32 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d2',
        name: 'Qwen Cloud GPU Level API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [608, -416],
    })
    QwenCloudGpuLevelApi = {
        method: 'POST',
        url: 'http://host.docker.internal:8006/openclaw/agent/level',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", system_context: (($json.levelMessages ?? []).find((message) => message.role === "system")?.content ?? ""), user_message: $json.prompt, history: $json.levelHistory, messages: $json.levelMessages, enable_thinking: false, use_lora: false, use_rag: false, temperature: 0.2, top_p: 0.8, max_new_tokens: 32 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b8',
        name: 'Format Level response',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [784, 16],
    })
    FormatLevelResponse = {
        jsCode: `const response = $input.first().json;
const candidate = [response.reply, response.raw?.normalized_level, response.raw?.choices?.[0]?.message?.content, response.output_text]
    .filter((value) => value !== undefined && value !== null).map(String).join(' ');
const match = candidate.match(/[1-4]/);
if (!match) throw new Error('Qwen Level returned no valid level 1-4');

const level = match[0];
const input = $('Route chat command (/level /v3 /v4)').first().json;
const requestedRoute = input.requestedRoute ?? '';
const route = requestedRoute === 'rag' || requestedRoute === 'v4_rag'
    ? 'v4'
    : requestedRoute === 'level'
        ? 'level'
        : requestedRoute === 'v3' || requestedRoute === 'v4'
            ? requestedRoute
            : Number(level) === 3 ? 'v4' : 'v3';

return [{ json: {
    ...input,
    level,
    route,
    prompt: input.prompt,
    modelMessages: input.modelMessages,
    output: level,
    text: level,
    model: 'Qwen3.5-4B-V4',
} }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d3',
        name: 'Format Cloud GPU Level response',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [816, -416],
    })
    FormatCloudGpuLevelResponse = {
        jsCode: `const response = $input.first().json;
const candidate = [response.reply, response.response, response.raw?.normalized_level, response.raw?.choices?.[0]?.message?.content, response.output_text]
    .filter((value) => value !== undefined && value !== null).map(String).join(' ');
const match = candidate.match(/[1-4]/);
if (!match) throw new Error('Cloud GPU Level returned no valid level 1-4');
const level = match[0];
const input = $('Route chat command (/level /v3 /v4)').first().json;
const requestedRoute = input.requestedRoute ?? '';
const route = requestedRoute === 'rag' || requestedRoute === 'v4_rag'
    ? 'v4'
    : requestedRoute === 'level'
        ? 'level'
        : requestedRoute === 'v3' || requestedRoute === 'v4'
            ? requestedRoute
            : Number(level) === 3 ? 'v4' : 'v3';
return [{ json: { ...input, level, route, prompt: input.prompt, modelMessages: input.modelMessages, output: level, text: level, model: 'Qwen3.5-4B-V4' } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b1',
        name: 'Is V4?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [1328, 192],
    })
    IsV4 = {
        conditions: {
            options: {
                caseSensitive: true,
                leftValue: '',
                typeValidation: 'strict',
                version: 2,
            },
            conditions: [
                {
                    id: 'v4-route-condition',
                    leftValue: '={{ $json.route }}',
                    rightValue: 'v4',
                    operator: {
                        type: 'string',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b2',
        name: 'Qwen V3 API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1536, 432],
    })
    QwenV3Api = {
        method: 'POST',
        url: '={{ $json.device === "cloud_gpu" ? "http://host.docker.internal:8006/openclaw/agent/run" : "http://host.docker.internal:8005/generate" }}',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V3", messages: $json.modelMessages, enable_thinking: false, use_lora: false, use_rag: false, max_new_tokens: 512, temperature: 0.5, top_p: 0.9 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b3',
        name: 'Format V3 response',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1808, 432],
    })
    FormatV3Response = {
        jsCode: `const response = $input.first().json;
const content = response.response ?? response.raw?.choices?.[0]?.message?.content;
if (typeof content !== 'string' || !content.trim()) throw new Error('Qwen V3 returned no response');
const input = $('Format Level response').first().json;
return [{ json: { output: content.trim(), text: content.trim(), model: 'Qwen3.5-4B-V3', level: input.level } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b4',
        name: 'Qwen V4 API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1536, 272],
    })
    QwenV4Api = {
        method: 'POST',
        url: '={{ $json.device === "cloud_gpu" ? "http://host.docker.internal:8006/openclaw/agent/run" : "http://host.docker.internal:8005/openclaw/agent/run" }}',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", messages: $json.modelMessages, enable_thinking: false, use_lora: true, use_rag: false, rag_top_k: 4, max_tokens: 512, temperature: 0.5, top_p: 0.9 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20b5',
        name: 'Format V4 response',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1744, 272],
    })
    FormatV4Response = {
        jsCode: `const response = $input.first().json;
const content = response.reply ?? response.raw?.choices?.[0]?.message?.content ?? response.output_text;
if (typeof content !== 'string' || !content.trim()) throw new Error('Qwen V4 returned no reply');
const input = $('Format Level response').first().json;
return [{ json: { output: content.trim(), text: content.trim(), model: 'Qwen3.5-4B-V4', level: input.level } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c6',
        name: 'Is RAG?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [1136, 32],
    })
    IsRag = {
        conditions: {
            options: {
                caseSensitive: false,
                leftValue: '',
                typeValidation: 'strict',
                version: 2.2,
            },
            conditions: [
                {
                    id: 'rag-route-condition',
                    leftValue:
                        '={{ ($json.level === "3" || ["rag", "v4_rag"].includes($json.requestedRoute)) ? "rag" : $json.requestedRoute }}',
                    rightValue: 'rag',
                    operator: {
                        type: 'string',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20cd',
        name: 'IBM Search API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1536, 80],
    })
    IbmSearchApi = {
        method: 'POST',
        url: 'http://host.docker.internal:8005/search/ibm',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", query: $json.prompt, messages: $json.modelMessages, top_k: 4 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20ce',
        name: 'Build V4 RAG prompt',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1792, 80],
    })
    BuildV4RagPrompt = {
        jsCode: `const search = $input.first().json;
if (search.ok !== true) throw new Error(search.error ?? 'IBM search failed');
const input = $('Format Level response').first().json;
const context = String(search.context ?? '').trim();
if (!context) throw new Error('IBM search returned empty context');
const sourceMessages = Array.isArray(input.modelMessages) ? input.modelMessages : [];
const messages = sourceMessages.map((message) => ({ ...message }));
let lastUserIndex = -1;
for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'user') {
        lastUserIndex = index;
        break;
    }
}
const ragGuide = 'Dùng ngữ cảnh truy xuất nếu liên quan. Trả lời ngắn gọn bằng tiếng Việt. Không bịa thông tin. Ngữ cảnh truy xuất:\\n' + context;
if (lastUserIndex >= 0) {
    const lastUser = String(messages[lastUserIndex].content ?? '').trim();
    messages[lastUserIndex].content = (ragGuide + '\\n\\n' + lastUser).trim();
} else {
    messages.push({ role: 'user', content: ragGuide });
}
return [{ json: { ...input, modelMessages: messages, search_query: search.query, search_results: search.results, retrieved_context: context } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c7',
        name: 'Qwen V4 RAG Answer API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [2016, 80],
    })
    QwenV4RagAnswerApi = {
        method: 'POST',
        url: 'http://host.docker.internal:8005/openclaw/agent/run',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", system_context: (($json.modelMessages ?? []).find((message) => message.role === "system")?.content ?? ""), messages: $json.modelMessages, enable_thinking: false, use_lora: false, use_rag: true, max_tokens: 512, temperature: 0.5, top_p: 0.9 }) }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c8',
        name: 'Format V4 RAG answer',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [2240, 80],
    })
    FormatV4RagAnswer = {
        jsCode: `const response = $input.first().json;
const content = response.reply ?? response.raw?.choices?.[0]?.message?.content ?? response.output_text;
if (typeof content !== 'string' || !content.trim()) throw new Error('Qwen V4 RAG answer returned no response');
const input = $('Format Level response').first().json;
return [{ json: {
    output: content.trim(),
    text: content.trim(),
    model: 'Qwen3.5-4B-V4',
    level: input.level,
    route: 'rag',
    use_rag: false,
    search_query: input.search_query,
    retrieved_context: input.retrieved_context,
} }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d4',
        name: 'Is Cloud GPU RAG?',
        type: 'n8n-nodes-base.if',
        version: 2.2,
        position: [1040, -416],
    })
    IsCloudGpuRag = {
        conditions: {
            options: {
                caseSensitive: false,
                leftValue: '',
                typeValidation: 'strict',
                version: 2.2,
            },
            conditions: [
                {
                    id: 'cloud-gpu-rag-level-condition',
                    leftValue: '={{ $json.level === "3" || ["rag", "v4_rag"].includes($json.requestedRoute) }}',
                    rightValue: true,
                    operator: {
                        type: 'boolean',
                        operation: 'equals',
                    },
                },
            ],
            combinator: 'and',
        },
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d5',
        name: 'Qwen Cloud GPU V4 RAG API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1344, -480],
    })
    QwenCloudGpuV4RagApi = {
        method: 'POST',
        url: 'http://host.docker.internal:8006/openclaw/agent/run',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ (() => { const messages = Array.isArray($json.modelMessages) ? $json.modelMessages : []; const system = messages.find((message) => message.role === "system"); const users = messages.map((message) => message.role === "user" ? String(message.content ?? "").trim() : "").filter(Boolean); const userMessage = users.length ? users[users.length - 1] : String($json.prompt ?? "").trim(); const history = messages.filter((message) => message.role !== "system").slice(0, -1); return JSON.stringify({ model: "Qwen3.5-4B-V4", model_code: "qwen-3.5/qwen-3.5-ubuntu", system_context: String(system?.content ?? ""), user_message: userMessage, history, scenario: "customer_consulting", options: { mode: "run", need_decision: true, allow_tool_call: true, max_history: 20 }, messages, enable_thinking: false, use_lora: false, use_rag: true, rag_top_k: 4, max_tokens: 512, temperature: 0.5, top_p: 0.9 }); })() }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d6',
        name: 'Format Cloud GPU V4 RAG answer',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1616, -480],
    })
    FormatCloudGpuV4RagAnswer = {
        jsCode: `const response = $input.first().json;
const content = response.reply ?? response.response ?? response.raw?.choices?.[0]?.message?.content ?? response.output_text;
if (typeof content !== 'string' || !content.trim()) throw new Error('Cloud GPU V4 RAG returned no response');
const input = $('Format Cloud GPU Level response').first().json;
return [{ json: { output: content.trim(), text: content.trim(), model: 'Qwen3.5-4B-V4', level: input.level, route: 'rag', device: 'cloud_gpu', use_rag: true } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d7',
        name: 'Qwen Cloud GPU V4 API',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [1344, -256],
    })
    QwenCloudGpuV4Api = {
        method: 'POST',
        url: 'http://host.docker.internal:8006/openclaw/agent/run',
        sendHeaders: true,
        specifyHeaders: 'json',
        jsonHeaders: '{"Content-Type":"application/json; charset=utf-8"}',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ (() => { const messages = Array.isArray($json.modelMessages) ? $json.modelMessages : []; const system = messages.find((message) => message.role === "system"); const users = messages.map((message) => message.role === "user" ? String(message.content ?? "").trim() : "").filter(Boolean); const userMessage = users.length ? users[users.length - 1] : String($json.prompt ?? "").trim(); const history = messages.filter((message) => message.role !== "system").slice(0, -1); return JSON.stringify({ model: "Qwen3.5-4B-V4", model_code: "qwen-3.5/qwen-3.5-ubuntu", system_context: String(system?.content ?? ""), user_message: userMessage, history, scenario: "customer_consulting", options: { mode: "run", need_decision: true, allow_tool_call: true, max_history: 20 }, messages, enable_thinking: false, use_lora: true, use_rag: false, rag_top_k: 4, max_tokens: 512, temperature: 0.5, top_p: 0.9 }); })() }}',
        options: {
            timeout: 120000,
        },
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20d8',
        name: 'Format Cloud GPU V4 response',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [1616, -256],
    })
    FormatCloudGpuV4Response = {
        jsCode: `const response = $input.first().json;
const content = response.reply ?? response.response ?? response.raw?.choices?.[0]?.message?.content ?? response.output_text;
if (typeof content !== 'string' || !content.trim()) throw new Error('Cloud GPU V4 returned no response');
const input = $('Format Cloud GPU Level response').first().json;
return [{ json: { output: content.trim(), text: content.trim(), model: 'Qwen3.5-4B-V4', level: input.level, route: 'v4', device: 'cloud_gpu', use_rag: false } }];`,
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20c9',
        name: 'View Level input log',
        type: 'n8n-nodes-base.readWriteFile',
        version: 1.1,
        position: [752, -192],
    })
    ViewLevelInputLog = {
        fileSelector: '/home/node/.n8n-files/qwen-log-api/agent_level_input.json',
        options: {},
    };

    @node({
        id: '2f47be3b-91d7-4d22-9ac2-6c68ef1d20ca',
        name: 'View Level output log',
        type: 'n8n-nodes-base.readWriteFile',
        version: 1.1,
        position: [912, -192],
    })
    ViewLevelOutputLog = {
        fileSelector: '/home/node/.n8n-files/qwen-log-api/agent_level_output.json',
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.RunTestData.out(0).to(this.TestInputChangeRouteHere.in(0));
        this.TestInputChangeRouteHere.out(0).to(this.RouteChatCommandLevelV3V4.in(0));
        this.WhenChatMessageReceived.out(0).to(this.RouteChatCommandLevelV3V4.in(0));
        this.OpenclawChatReceived.out(0).to(this.Openclaw.in(0));
        this.Openclaw.out(0).to(this.RouteChatCommandLevelV3V4.in(0));
        this.RouteChatCommandLevelV3V4.out(0).to(this.IsCloudGpu.in(0));
        this.IsCloudGpu.out(0).to(this.QwenCloudGpuLevelApi.in(0));
        this.IsCloudGpu.out(1).to(this.QwenLevelApi.in(0));
        this.QwenLevelApi.out(0).to(this.FormatLevelResponse.in(0));
        this.QwenLevelApi.out(0).to(this.ViewLevelInputLog.in(0));
        this.QwenLevelApi.out(0).to(this.ViewLevelOutputLog.in(0));
        this.QwenCloudGpuLevelApi.out(0).to(this.FormatCloudGpuLevelResponse.in(0));
        this.FormatLevelResponse.out(0).to(this.IsLevel.in(0));
        this.IsLevel.out(1).to(this.IsRag.in(0));
        this.FormatCloudGpuLevelResponse.out(0).to(this.IsCloudGpuRag.in(0));
        this.IsRag.out(0).to(this.IbmSearchApi.in(0));
        this.IsRag.out(1).to(this.IsV4.in(0));
        this.IsCloudGpuRag.out(0).to(this.QwenCloudGpuV4RagApi.in(0));
        this.IsCloudGpuRag.out(1).to(this.QwenCloudGpuV4Api.in(0));
        this.IbmSearchApi.out(0).to(this.BuildV4RagPrompt.in(0));
        this.BuildV4RagPrompt.out(0).to(this.QwenV4RagAnswerApi.in(0));
        this.IsV4.out(0).to(this.QwenV4Api.in(0));
        this.IsV4.out(1).to(this.QwenV3Api.in(0));
        this.QwenV3Api.out(0).to(this.FormatV3Response.in(0));
        this.QwenV4Api.out(0).to(this.FormatV4Response.in(0));
        this.QwenV4RagAnswerApi.out(0).to(this.FormatV4RagAnswer.in(0));
        this.QwenCloudGpuV4RagApi.out(0).to(this.FormatCloudGpuV4RagAnswer.in(0));
        this.QwenCloudGpuV4Api.out(0).to(this.FormatCloudGpuV4Response.in(0));
    }
}
