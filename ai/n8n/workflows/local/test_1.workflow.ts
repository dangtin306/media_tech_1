import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : test_1
// Nodes   : 3  |  Connections: 2
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// WhenClickingExecuteWorkflow        manualTrigger
// WhenChatMessageReceived            chatTrigger
// AiAgent                            agent
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// WhenClickingExecuteWorkflow
//    → AiAgent
// WhenChatMessageReceived
//    → AiAgent (↩ loop)
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: 'OqlVod0flxqPWVM8',
    name: 'test_1',
    active: false,
    isArchived: false,
    projectId: 'W6XGlfo1EVdrxhD5',
    settings: { executionOrder: 'v1', binaryMode: 'separate', availableInMCP: false },
})
export class Test1Workflow {
    // =====================================================================
    // CONFIGURATION DES NOEUDS
    // =====================================================================

    @node({
        id: '84e87817-ff67-4964-aeb9-df2eeb2fb579',
        name: 'When clicking ‘Execute workflow’',
        type: 'n8n-nodes-base.manualTrigger',
        version: 1,
        position: [0, 0],
    })
    WhenClickingExecuteWorkflow = {};

    @node({
        id: '2105130e-1f1d-450e-ac4a-cd63622d9604',
        webhookId: '4dbec87c-b50c-4c47-8202-2bcdb6c57919',
        name: 'When chat message received',
        type: '@n8n/n8n-nodes-langchain.chatTrigger',
        version: 1.4,
        position: [208, 0],
    })
    WhenChatMessageReceived = {
        options: {},
    };

    @node({
        id: 'f0bf7f71-255b-4865-baf4-918e40c0f35b',
        name: 'AI Agent',
        type: '@n8n/n8n-nodes-langchain.agent',
        version: 3.1,
        position: [416, 0],
    })
    AiAgent = {
        options: {},
    };

    // =====================================================================
    // ROUTAGE ET CONNEXIONS
    // =====================================================================

    @links()
    defineRouting() {
        this.WhenClickingExecuteWorkflow.out(0).to(this.AiAgent.in(0));
        this.WhenChatMessageReceived.out(0).to(this.AiAgent.in(0));
    }
}
