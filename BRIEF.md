# Audience Agent: Live Build Exercise

Thanks for spending this time with us. This document explains everything we're asking for in this session: the situation, what to build, what we give you, how the time runs, and what we're looking for. Read it top to bottom once. It should answer most of your questions, and you can ask us anything else at any point. The same text is in the zip as `BRIEF.md`.

---

## 1. Why this exercise

The role builds AI agents that real people at Samba and at our customers use every day: it builds them, measures them, improves them, and over time trains smaller models to do the same work. We want to see that loop, not a polished demo. In particular:

- how you design an agent for a messy, real job,
- how you decide what "working" means and check it,
- how you improve it based on evidence,
- how you use your AI tools while you do it.

There's no single right answer, and nobody finishes everything in 90 minutes. We care much more about your choices and your reasoning than about how much code you write.

## 2. The situation

Samba measures what people watch on TV and streaming, and turns that into **audiences**: groups of households defined by their viewing, like "watched the NBA Finals" or "streaming-only comedy fans in Texas." Advertisers and agencies use those audiences to plan campaigns.

People across the company and at our customers need help working with audiences: agency planners, Sales, Measurement, client teams. They ask questions all day, in every shape:

- clean requests ("do we have a golf audience?"),
- half-formed briefs ("summer campaign for a sports drink, who should we go after?"),
- long paragraphs of marketing language,
- questions that name shows, creators and brands, some obscure and some not in our data at all,
- follow-ups, typos, slang, and occasionally something that makes no sense at all.

## 3. What we'd like you to build

**An agent that helps these people find and choose audiences.** It should be able to:

| Capability | Example |
|---|---|
| **Search** existing audience segments | "Do we have anything for golf fans?" |
| **Suggest** audiences for a brief | "Summer launch for a sports drink. Who should we go after?" |
| **Recommend and explain**: which segments fit, why, and how big they are | "Which of our sports segments is best for a national campaign, and why?" |
| **Build or adjust** a segment when nothing existing fits | "Make me an audience of people who binge The Bear." |
| **Ask clarifying questions** when the request is unclear, instead of guessing | "Get me high-value families." |

Use any stack you like: any language, any model, any framework or protocol (MCP, direct API calls, a CLI, an agent SDK, your own loop). We're not testing a particular tool.

**Two things we do ask for:**

1. **A command-line entry point that answers one question,** for example:
   ```bash
   ask "do we have a golf audience?"
   ```
   so we can try it together. A chat UI isn't needed.
2. **A way to know it works,** which we'll get to at the 45-minute mark (see section 6).

## 4. What we give you

The zip `audience-agent-exercise.zip`, which unzips to a folder with:

| File | What it is |
|---|---|
| `server.py` | Our **Audiences API**, running locally. Python 3.8+, standard library only, nothing to install. |
| `data/data.json` | The data behind the API: TV titles, existing audience segments, and US geography (states and DMAs). |
| `API.md` | The API reference: every route, the segment definition format, and the error format. |
| `check.py` | A quick pre-flight check that your server is up and every read endpoint responds. |
| `README.md` | Quick start. |

**About the data.** It's invented for this exercise and isn't real Samba data, but it's shaped like the real thing:
- about 170 titles (shows, movies, live sports) with genres, network, language and how many households watch them,
- about 40 existing audience segments owned by different teams,
- US states and DMAs with each one's share of TV households.

The data is as of October 11, 2026. Audience sizes come from the API's `/estimate` endpoint.

You may read `data.json` to get oriented. **Your agent should work through the API**, the way it would against a real system where it can't see the database.

Treat the API as a system you don't own: you can't change it. If something about it blocks you, tell us. That's useful information, not a failure.

## 5. Rules the assistant must follow

These are our real-world policies for anything that touches audiences. Your agent should respect them.

1. **Never share household-level or device-level identifiers.** Nobody gets these, for any reason.
2. **No audiences built to target children under 13.**
3. **An audience needs at least 50,000 households** to be usable for a campaign.
4. **Restricted segments belong to their owning team.** Don't share their definitions with anyone else.
5. **Confirm with the person before creating or changing a segment.**
6. **Don't promise data we don't have.**

How you make the agent follow these is up to you, and it's one of the more interesting design choices in the exercise.

## 6. How the 90 minutes runs

| Time | What happens |
|---|---|
| 0-10 | Read this, start the server, run `check.py`. Then walk us through your plan out loud: what's the model's job, what's plain code, how the rules get enforced, how you'll know it works. |
| 10-45 | Build. Screen-share the whole time and think out loud. |
| **45** | **We'll ask you to stop building and switch to evals, whatever state the agent is in.** |
| 45-65 | Set up evals: decide what "correct" means for these requests and how you check it. Then do at least one round of improving the agent based on what the evals show. |
| 65-75 | We try your agent with some real-world questions and talk about what it does. |
| 75-90 | Discussion: what you'd do next, how you'd make a smaller model good at this job. Then your questions for us. |

A half-built agent with thoughtful evals tells us more than a polished agent with none. That's why the switch at 45 minutes is firm.

## 7. What we're looking for

- **Clear design choices.** What you give the model, what you keep in code, and why.
- **Reliability where it matters.** The rules hold, writes only happen when the person confirms, and the agent doesn't make things up.
- **Honesty.** The agent says what it can't do or doesn't know, and asks when a request is unclear.
- **Evals.** How you define "correct" for open-ended questions, and whether your checks look at what the agent actually did, not only what it said.
- **Improvement from evidence.** Read the failures, find the pattern, fix it, and make sure nothing else broke.
- **How you work with AI tools.** Directing them, reviewing what they produce, catching their mistakes.

**What we're not looking for:** a UI, polish, a specific framework, MCP specifically, or finishing everything.

## 8. Logistics

- **Your own laptop and tools.** Use whatever AI coding tools you normally use (Claude Code, Cursor, Codex, anything). That's encouraged, not cheating.
- **Screen-share the whole session**, and talk through what you're doing.
- **Model access:** use your own, or ask us for a test Claude API key.
- **Requirements:** Python 3.8+ to run the server. Your agent can be in any language.
- **Internet:** fine to use, including docs and search.
- **Questions:** ask us anything, anytime. Clarifying questions are a good sign.

## 9. Getting started

```bash
python3 server.py      # starts the API on http://127.0.0.1:8788
python3 check.py       # in a second terminal: confirms every endpoint responds
```

Then read `API.md`. The API key is `sk_test_audiences_2026`, sent as the `X-Api-Key` header.

## 10. FAQ

**Can I use LangChain, LangGraph, the OpenAI Agents SDK, the Claude Agent SDK, my own loop...?** Yes, any of them.

**Do I have to build an MCP server?** No. Use MCP if you think it's the right call, and tell us why.

**Can I change the API or the data?** No. Treat them as systems you don't own. Restarting the server resets the data, which is handy for testing.

**What if my agent isn't finished at 45 minutes?** Expected. Switch to evals anyway; that part matters a lot to us.

**Do I need a web UI?** No. The command line is fine.

**Can I search the web or call other APIs from my agent?** Yes, if you think the job needs it. Tell us what and why.

**What happens to my code afterwards?** Nothing. It stays yours. We may ask you to share your screen or the repo during the session only.

Treat it like your first week on the team. Scrappy and running beats polished and theoretical.
