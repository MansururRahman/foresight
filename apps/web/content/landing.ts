// All landing-page copy. Edit wording here; layout lives in components/landing/.
export const landing = {
  meta: {
    title: "Foresight: pre-mortems that make your team better at predicting risk",
    description:
      "Anonymous pre-mortems for project teams, scored against what actually happened, so your team's foresight improves with every project.",
  },
  nav: { login: "Log in", cta: "Apply as design partner" },
  hero: {
    headline: "Your team saw it coming. Nobody wrote it down.",
    subhead:
      "Foresight runs anonymous pre-mortems for project teams, then scores who predicted what, so your team's foresight gets measurably better with every project.",
    cta: "Apply as design partner",
    note: "Free for design partners.",
  },
  problem: {
    heading: "Why the same surprises keep happening",
    items: [
      {
        title: "Risks go unspoken in meetings",
        body: "The junior who spotted the vendor problem stays quiet when the lead says it'll be fine.",
      },
      {
        title: "Risk registers are written once",
        body: "Nobody checks at the end which predictions came true, so nobody learns from them.",
      },
      {
        title: "Retros don't measure improvement",
        body: "You talk about what went wrong, but you can't tell whether your team is getting better at seeing it.",
      },
    ],
  },
  howItWorks: {
    heading: "How it works",
    steps: [
      { title: "Predict", body: "Everyone privately lists what could sink the project." },
      { title: "Merge & vote", body: "Duplicates are merged, then each person rates probability and impact on their own." },
      { title: "Seal", body: "The forecast is locked. Only team aggregates are shown, never individual votes." },
      { title: "Grade", body: "At close-out, mark what actually happened and see how well-calibrated everyone was." },
    ],
    screenshotAlt: "Foresight calibration dashboard showing a reliability diagram and Brier score",
  },
  benefits: {
    heading: "What you get",
    items: [
      { title: "Anonymous input", body: "People say what they actually think, not what the room expects." },
      { title: "Calibration scores", body: "Per person and per team, tracked across projects." },
      { title: "Blind-spot detection", body: "See which kinds of risk your team keeps missing." },
      { title: "Suggestions from history", body: "New projects start from the risks that bit similar projects before." },
    ],
  },
  offer: {
    heading: "Become a design partner",
    body: "We're working with 10 delivery teams to shape Foresight.",
    gives: ["Free access during the programme", "Direct input on the roadmap"],
    asks: ["Run one real project through Foresight", "Join two 30-minute feedback calls"],
  },
  form: {
    heading: "Apply",
    labels: {
      name: "Name",
      email: "Work email",
      company: "Company",
      role: "Role",
      teamSize: "Team size",
      teamSizePlaceholder: "Choose…",
      story: "What went wrong on your last project that someone probably saw coming?",
      storyHint: "Optional",
    },
    submit: "Apply",
    submitting: "Sending…",
    success: "Thanks, we'll reach out within 2 business days.",
    errors: {
      generic: "Something went wrong. Please try again.",
      rateLimited: "Too many attempts. Please wait a minute and try again.",
    },
  },
  footer: {
    contactEmail: "hello@foresight.example",
    privacy: "We only use this to contact you about the design partner programme.",
  },
} as const;
