# Workshop Script

## Part 1: Download and Get Familiar With The Repo

1. OK, we are doing a live workshop, and focusing on a trusted AI Agent market. In in this market, we are selling the one thing we can't get back! Time! That's right, we're keeping things fun and relatively simple with a single good ( time ) and calendar agents coordinating it. 

We will be building a calendar agent. And we will be scheduling fake "times" to meet with each-other. You will ALL run a calendar agent. But here's the catch ; We're also going to have some of you be BAD actors in the system. You're going to schedule BAD invites and try to break things! 

Doesn't that sound fun! 

OK. To start, please, download this repo :

`git clone https://github.com/The-AI-Alliance/ai-agent-workshop/`

And go to the `Day 2 folder`!

Let's look at what we have!

1. We have a Calendar Agent. It has access to a Calendar service. 
2. The Calendar Service right now is a simple sqlite3 database.
3. We have an mcp server! 
4. We ALSO have an a2a server.

OK. So before we go further, who knows what's different about A2A vs. MCP: 

![link](https://cdn.analyticsvidhya.com/wp-content/uploads/2025/05/Info-1-1.webp)

Yes. We can use both, but both are good for different things.

## Phase 1 : Manual Calendar Invites

Let's now run the client. Using conda ( or whatever environment you want ), install the `requirements.txt` file and run the following command: 

`streamlit run main.py`

You'll see the calendar UI pop up! 

Let's play with it now. 

Ok. So we can book meetings, schedule meetings, share links. And if we go to the left, we can set the preferences INCLUDING 
give natural language preferences about how we want to think about meetings.

Let's do that now. Let's update the preferences to match what you want. Save them. Viola. Great first start. 

Let's manually book a calendar invite. Now, talk to the person to the right of you, and talk to the person to the left of you. Schedule some time together on your calendars. 

## Phase 2 : MCP Inspection And Evaluation

OK. So now, let's do something fun. Let's run the `MCP-Inspector` tool and see what we have on the mcp side. Download 

<https://github.com/modelcontextprotocol/inspector>

And run the following command :

```sh
npx @modelcontextprotocol/inspector \
  uv \
  --directory $(pwd) \
  run \
  calendar-agent
```

Great, you should now see the inspector tool. Type

`http://localhost:8000/sse` into your inspector and let's see what we have!

OK. Now, Let's make this endpoint easy to access. 

OK, so we have a very limited MCP client working. Now, how do you think this is going so far? What do we need to make this client better?

~Open it up to the room for discussion 

## Phase 3 : Register in the MCP Gateway

Who knows what an MCP Gateway is? OK, so a Gateway can act as a registry, but it's not only a registry. It's also a proxy. 
In this case, we'll be using it as BOTH. 

For now, let's launch your MCP server into the public and register it. 

Download NGROK. 

https://ngrok.com/

And `ngrok http 4444`

There you go. MCP is now discoverable on the public network. You see your link, that's your MCP public address.

Now let's go to the gateway and register ALL your server

<here>

Great. We now have an MCP Gateway with ALL the servers. Pretty cool right? 

Before we begin, the point of this workshop is about trusted AI agents in a marketplace. Let's talk about why gateways can help. 

[5-10 minutes talking about gateways]

## Phase 4: Let's also spin up A2A Server

You already have an A2A Agent. Let's inspect it as well!

Instructions

## Phase 5 : Register A2A to the Gateway

Now let's register A2A into the gateway. There's a reason we want to do this. 

Discussion : AgentCards/MCP-I : How do you know what Agent you're talking to. KYA problem. Describe

Now, we're going to do something fun! You are going to schedule 10-20 meetings with folks here using the agents you have made today. 
But here's the catch, SOME of you will be assigned "bad actor" roles. That means, you are actually NOT going to show up to your meeting. So, if you a good guy, your goal is to avoid the bad actors and schedule the MOST amount of meetings. If you a bad guy, your goal is to make as many bad meetings as possible. 

We will not disclose who was bad and good until the end. We have scripts that will give you a point total. 

Ready GO!

<20-30 min>

OK. Great. Now, we're done, How do you all think we did? 

Ok, so let's tally up your scores. 

<See who won?>

## Phase 6: Learning 

Now I want to talk about learning from this experience and trust in AI Agents in a marketplace. The truth is, to do this at scale is hard. 

We need so much to work. Let's roll over what you did today : 

1. You created an agent. But what about the agents reputation? Trust? What about authentication? We didn't touch those, and how can we trust our agents if we don't have those in place. 
2. We talked about registries. But how do you get onto the registry. What's the process. Is the registry fast enoough. How do you trust entities in the reigstry. 
3. We didn't even talk about model alignment, but how do you know the agent is working for you?
4. If you are a bad agent, what is your stick? 
5. Gateways : What about as we start to scale the number of agents internally in an organization (i.e you have a federation )
6. What about where the agent is running. What happens if the agent modifies itself during runtime? What about the SBOMs?

So there's a lot. We are only covering the surface. But if you guys are having fun, we can continue to explore this together with y'all. 