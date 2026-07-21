import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : test_2 - Qwen 3.5 4B chat
// Nodes   : 3  |  Connections: 2
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// WhenChatMessageReceived            chatTrigger
// Qwen354b                           httpRequest
// FormatQwenReply                    code
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// WhenChatMessageReceived
//    → Qwen354b
//      → FormatQwenReply
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'yJRYT0KzPlheIhyt',
    name: 'test_2 - Qwen 3.5 4B chat',
    active: false,
    isArchived: false,
    settings: { executionOrder: 'v1', binaryMode: 'separate', availableInMCP: false },
})
export class Test2Qwen354bChatWorkflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: '2105130e-1f1d-450e-ac4a-cd63622d9610',
        webhookId: '4dbec87c-b50c-4c47-8202-2bcdb6c57920',
        name: 'When chat message received',
        type: '@n8n/n8n-nodes-langchain.chatTrigger',
        version: 1.4,
        position: [0, 0],
    })
    WhenChatMessageReceived = {
        options: {},
    };

    @node({
        id: '7f7b4d0d-2c9d-4b7d-9e7a-1f0f5c4a2a12',
        name: 'Qwen 3.5 4B',
        type: 'n8n-nodes-base.httpRequest',
        version: 4.2,
        position: [260, 0],
    })
    Qwen354b = {
        method: 'POST',
        url: 'http://host.docker.internal:8005/v1/chat/completions',
        sendBody: true,
        specifyBody: 'json',
        jsonBody:
            '={{ JSON.stringify({ model: "Qwen3.5-4B-V4", messages: [{ role: "user", content: $json.chatInput || $json.text || $json.message || "" }], enable_thinking: false, use_lora: false, use_rag: false, max_tokens: 512, temperature: 0.5, top_p: 0.9 }) }}',
        options: {},
    };

    @node({
        id: '7f7b4d0d-2c9d-4b7d-9e7a-1f0f5c4a2a13',
        name: 'Format Qwen reply',
        type: 'n8n-nodes-base.code',
        version: 2,
        position: [520, 0],
    })
    FormatQwenReply = {
        mode: 'runOnceForAllItems',
        jsCode: `const response = $input.first().json;
const content = response.choices?.[0]?.message?.content ?? response.reply ?? response.response ?? JSON.stringify(response);
return [{ json: { output: content, text: content } }];`,
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.WhenChatMessageReceived.out(0).to(this.Qwen354b.in(0));
        this.Qwen354b.out(0).to(this.FormatQwenReply.in(0));
    }
}
