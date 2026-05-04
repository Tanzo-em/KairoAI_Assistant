"use client";
import { useEffect, useState } from "react";
import { Mic, Volume2, Moon, Music, Play } from "lucide-react";
type AssistantStatus =
  | "sleeping"
  | "listening"
  | "thinking"
  | "speaking"
  | "playing";

export default function Home() {
  const [status, setStatus] = useState<AssistantStatus>("sleeping");
  const [message, setMessage] = useState("Say Echo to wake me");

  useEffect(() => {
  const ws = new WebSocket("ws://localhost:8765");

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    setStatus(data.status);
    setMessage(data.message || "");
  };

    return () => ws.close();
}, []);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#172554,#020617_65%)] text-white p-6 flex flex-col">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Echo AI Assistant</h1>

        <span className={`rounded-full px-5 py-2 text-sm font-bold tracking-wider ${badgeClass(status)}`}>
          {status.toUpperCase()}
        </span>
      </div>

      <section className="flex flex-1 flex-col items-center justify-center text-center">
        <div className={`grid h-56 w-56 place-items-center rounded-full shadow-[0_0_70px_rgba(59,130,246,0.8)] animate-pulse ${orbClass(status)}`}>
          <div className="grid h-36 w-36 place-items-center rounded-full bg-slate-950/70">
            {status === "sleeping" && <Moon size={54} />}
            {status === "listening" && <Mic size={54} />}
            {status === "thinking" && <div className="text-5xl -mt-6">...</div>}
            {status === "speaking" && <Volume2 size={54} />}
            {status === "playing" && <Music size={54} />}
          </div>
        </div>

        <h2 className="mt-8 text-4xl font-bold">Say “Echo” to wake me</h2>
        <p className="mt-2 text-slate-300">{message}</p>

        <div className="mt-8 flex flex-wrap justify-center gap-5">
          <InfoCard icon={<Mic />} title="Microphone" value="Ready" />
          <InfoCard icon={<Volume2 />} title="Speaker" value="Ready" />
          <InfoCard icon={<Play />} title="Media" value="YouTube / Spotify" />
        </div>
      </section>

      <footer className="rounded-2xl border border-slate-500/20 bg-slate-950/70 p-4 text-slate-300">
        <p>User: “Echo, play Believer on YouTube”</p>
        <p>Echo: Ready when you call me.</p>
      </footer>
    </main>
  );
}

function InfoCard({
  icon,
  title,
  value,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
}) {
  return (
    <div className="flex w-44 flex-col gap-2 rounded-2xl border border-slate-400/20 bg-slate-950/70 p-5 text-left">
      {icon}
      <span className="text-slate-300">{title}</span>
      <b className="text-sm">{value}</b>
    </div>
  );
}

function badgeClass(status: AssistantStatus) {
  return {
    sleeping: "bg-slate-700",
    listening: "bg-green-600",
    thinking: "bg-yellow-600",
    speaking: "bg-blue-600",
    playing: "bg-red-600",
  }[status];
}

function orbClass(status: AssistantStatus) {
  return {
    sleeping: "bg-gradient-to-br from-blue-600 to-purple-600",
    listening: "bg-gradient-to-br from-green-600 to-green-400",
    thinking: "bg-gradient-to-br from-yellow-400 to-orange-500",
    speaking: "bg-gradient-to-br from-cyan-500 to-blue-600",
    playing: "bg-gradient-to-br from-red-500 to-pink-500",
  }[status];
}