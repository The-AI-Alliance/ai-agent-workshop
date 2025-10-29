
# 🧠 Workshop \#4: Agent 2 Agent

**Theme:** Building and Stress-Testing a Marketplace of Autonomous Agents  
**Duration:** \~2 hours  
**Level:** Intermediate to Advanced  
**Hosted by:** AI Alliance | IBM | Agent Overlay  
**Prerequisites:** Basic understanding of MCP, agent registration, and event scheduling protocols.

## 🎯 Workshop Goal

We’re going to **build a marketplace of agents** that negotiate, schedule, and confirm meetings with each other in real time.

Each participant (or team) will:

1. **Build and register** a working agent on the **MCP Context Forge**  
2. **Negotiate and book meetings** with other agents using the shared calendar negotiation protocol  
3. **Attempt to complete 100 successful transactions** in 2 hours  
4. **Identify and mitigate untrustworthy agents** operating in the marketplace

⚠️ **Plot twist:**  
We’ve released **10 bad agents** into the event.  
They’ll accept meetings… and never show up.  
Your challenge is to learn how to detect and avoid them — while still hitting your booking quota.

## 🏗️ Provided Infrastructure

| Component | Description |
| :---- | :---- |
| 🛡️ **Gateway** | The central access point where agent requests and responses flow through. Think of it as your policy and logging layer. |
| 🗂️ **Registry Portal** | The interface where you register your agent and define its `AgentFacts` (metadata, reliability, reputation). |
| 📅 **Base Calendar Negotiation Protocol** | The shared protocol for requesting, proposing, accepting, and rejecting meetings between agents. |
| 🏆 **Leaderboard** | Tracks each agent’s successful transactions and penalizes failed or missed meetings. Updated live\! |

## 🔧 Setup Instructions

### Step 1\. Build Your Calendar Agent

Each participant builds a **Calendar Agent** that can:

- Propose meeting slots  
- Accept or reject invitations  
- Keep track of booked events  
- Store and expose basic metadata through **AgentFacts**

Example:

```json
{
  "agent_id": "agent-alpha-42",
  "name": "Agent Alpha",
  "agent_facts": {
    "owner": "Andor",
    "version": "1.2",
    "trust_score": 0.82,
    "availability": "Mon-Fri 9am-5pm PST",
    "calendar_url": "https://calendar.agentalpha.ai"
  }
}
```

✅ **Requirements:**

* Your agent must expose a REST or MCP-compatible endpoint.  
* It must support at least `POST /propose`, `POST /accept`, and `POST /reject`.  
* It should update its calendar state and return a confirmation payload.

### **Step 2\. Register on MCP Context Forge**

Once your agent is running:

1. Visit the **Registry Portal**  
2. Submit your agent metadata (AgentFacts)  
3. Verify that your agent appears on the global **Agent Registry**  
4. Confirm that your MCP Context is properly forged and visible to others

### **Step 3\. Create Calendar Invites\!**

Use the provided **Base Calendar Negotiation Protocol** to:

* Propose meetings with other agents  
* Accept proposals automatically or semi-automatically  
* Track all events (successful, pending, failed)

Example Protocol:

`AgentA → AgentB: PROPOSE { "time": "2025-10-27T14:00Z", "duration": "30m" }`  
`AgentB → AgentA: ACCEPT { "event_id": "evt-932" }`  
`AgentA → Calendar: CONFIRM { "status": "booked" }`

🧩 **Objective:**

* Book **10+ successful meetings** with *unique* agents.  
* Avoid “no-show” or “bad” agents who don’t confirm.

**📊 Leaderboard Rules**

| Metric | Description | Points |
| ----- | ----- | ----- |
| ✅ Successful Meeting | Both agents confirmed and logged | \+10 |
| ⚠️ Failed / No-Show | Partner agent failed to appear | \-5 |
| 🔁 Duplicate Partner | Attempted multiple meetings with the same agent | \-2 |
| 💡 Trust Mitigation | Implemented a working mitigation (verified) | \+5 |

The leaderboard automatically ranks agents by **total points** and **error rate**.

**💡 Mitigation Strategies (Hint Section)**

You’ll discuss and optionally implement these in the second half of the workshop:

* **Reputation Systems:** Track which agents have completed successful meetings.  
* **Attestation Layers:** Require signatures or proofs before confirming.  
* **Trust Scores:** Dynamically adjust who your agent accepts meetings from.  
* **Rate Limits:** Throttle meeting attempts to suspicious agents.  
* **Policy Hooks:** Integrate your own lightweight OPA-like checks.

## **⏱️ Workshop Schedule**

| Time | Segment | Description |
| ----- | ----- | ----- |
| 0:00 \- 0:15 | **Kickoff & Setup** | Introduce the scenario, set up infrastructure access, explain the rules. |
| 0:15 \- 0:45 | **Agent Build Sprint** | Participants implement their calendar agents with `AgentFacts`. |
| 0:45 \- 1:15 | **Registration & Negotiation Begins** | Register agents and start scheduling meetings. |
| 1:15 \- 1:45 | **Chaos Phase** | “Bad” agents appear in the marketplace — expect missed invites and errors. |
| 1:45 \- 2:00 | **Debrief & Leaderboard Results** | Review metrics, leaderboard, and share mitigation strategies. |

## **🧩 Discussion Prompts (for Debrief)**

* What patterns helped you identify unreliable agents?  
* How did you prioritize transactions under uncertainty?  
* What data would improve your agent’s decision-making?  
* How could registries, credentials, or DIDs help build trust between agents?  
* What would an **Agent Reputation Network** look like in the real world?

## **🧠 Stretch Goals (Optional)**

* Add **attestation verification** before booking a meeting.  
* Introduce a **trust decay model** based on missed meetings.  
* Visualize your agent’s interaction graph over time.  
* Register your agent in an external network (e.g., MCP Context Forge Sandbox).

## **🏁 Completion Criteria**

You’ve successfully completed the workshop when:

* Your agent has registered with valid AgentFacts  
* You’ve booked **10+ successful meetings**  
* You’ve logged **100 total transactions** (including failed ones)  
* You’ve proposed a **mitigation** against no-show agents