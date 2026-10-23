"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Button from "@/app/hr/_components/Button";
import { inputClass } from "@/app/hr/_components/Field";
import { EmptyState, ErrorNote } from "@/app/hr/_components/Modal";
import { TableSkeleton } from "@/app/hr/_components/Skeleton";
import {
  api,
  formatDate,
  type TalentPoolEntry,
} from "@/app/hr/_lib/api";

type SortKey = "fit" | "newest" | "oldest" | "name";

function initialsOf(name: string | null) {
  return (name ?? "?")
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Highlights the first case-insensitive match of `query` inside `text`. */
function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const index = text.toLowerCase().indexOf(q.toLowerCase());
  if (index === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded bg-navy-100 px-0.5 text-navy-900">
        {text.slice(index, index + q.length)}
      </mark>
      {text.slice(index + q.length)}
    </>
  );
}

export default function TalentPoolPage() {
  const [entries, setEntries] = useState<TalentPoolEntry[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("fit");
  const [jobFilter, setJobFilter] = useState("");
  const [skillFilter, setSkillFilter] = useState<string[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const pool = await api<TalentPoolEntry[]>("/talent-pool");
      setEntries(pool);
      setLoadError(null);
    } catch (caught) {
      setLoadError(
        caught instanceof Error ? caught.message : "Failed to load talent pool"
      );
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  // "/" jumps to the search box from anywhere on the page.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
      if (event.key === "/" && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Open jobs that at least one pool member fits, with how many fit each.
  const jobChips = useMemo(() => {
    const byJob = new Map<string, { id: string; title: string; count: number }>();
    for (const entry of entries ?? []) {
      for (const match of entry.matching_jobs ?? []) {
        const current = byJob.get(match.job_id);
        if (current) current.count += 1;
        else
          byJob.set(match.job_id, {
            id: match.job_id,
            title: match.job_title,
            count: 1,
          });
      }
    }
    return Array.from(byJob.values()).sort((a, b) => b.count - a.count);
  }, [entries]);

  // Skill chips only list skills that matter for the open jobs (or for the
  // selected job), never the candidates' general skill sets.
  const topSkills = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>();
    for (const entry of entries ?? []) {
      const pool = jobFilter
        ? (entry.matching_jobs ?? [])
            .filter((m) => m.job_id === jobFilter)
            .flatMap((m) => m.matched_skills)
        : (entry.relevant_skills ?? []);
      for (const skill of pool) {
        const key = skill.toLowerCase();
        const current = counts.get(key);
        if (current) current.count += 1;
        else counts.set(key, { label: skill, count: 1 });
      }
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0]))
      .slice(0, 14)
      .map(([key, value]) => ({ key, ...value }));
  }, [entries, jobFilter]);

  // Search terms: "python react" or "python, react" must ALL match somewhere
  // (name, email or a skill).
  const terms = useMemo(
    () =>
      search
        .toLowerCase()
        .split(/[\s,]+/)
        .filter(Boolean),
    [search]
  );

  // Filtering happens in memory, so results update on every keystroke.
  const visible = useMemo(() => {
    const rows = (entries ?? []).filter((entry) => {
      const jobMatch = jobFilter
        ? (entry.matching_jobs ?? []).find((m) => m.job_id === jobFilter)
        : undefined;
      if (jobFilter && !jobMatch) return false;
      const relevant = (
        jobMatch ? jobMatch.matched_skills : (entry.relevant_skills ?? [])
      ).map((skill) => skill.toLowerCase());
      if (!skillFilter.every((wanted) => relevant.includes(wanted))) return false;
      // Search still looks through every skill on the profile.
      const skills = (entry.skills ?? []).map((skill) => skill.toLowerCase());
      if (terms.length === 0) return true;
      const haystack = [
        entry.candidate_name ?? "",
        entry.candidate_email ?? "",
        ...skills,
      ]
        .join(" ")
        .toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
    const fitOf = (entry: TalentPoolEntry) => {
      const matches = entry.matching_jobs ?? [];
      if (jobFilter) return matches.find((m) => m.job_id === jobFilter)?.score ?? 0;
      return matches[0]?.score ?? 0;
    };
    rows.sort((x, y) => {
      if (sort === "fit") {
        const diff = fitOf(y) - fitOf(x);
        if (diff !== 0) return diff;
      }
      if (sort === "name") {
        return (x.candidate_name ?? "").localeCompare(y.candidate_name ?? "");
      }
      const diff =
        new Date(x.created_at).getTime() - new Date(y.created_at).getTime();
      return sort === "oldest" ? diff : -diff;
    });
    return rows;
  }, [entries, jobFilter, skillFilter, terms, sort]);

  if (loadError && !entries) {
    return (
      <div className="flex flex-col gap-3 p-6 sm:p-8">
        <ErrorNote message={loadError} />
        <div>
          <Button variant="secondary" onClick={() => void load()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }
  if (!entries) {
    return (
      <div className="flex flex-1 flex-col gap-6 p-6 sm:p-8">
        <div>
          <div className="skeleton h-6 w-40" />
          <div className="skeleton mt-2 h-3.5 w-72" />
        </div>
        <TableSkeleton rows={5} columns={4} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6 sm:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900">
          Talent Pool
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Previously reviewed candidates you may want to reconsider later.
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-zinc-900">Pool members</h2>
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium tabular-nums text-zinc-600">
            {visible.length === entries.length
              ? `${entries.length} total`
              : `${visible.length} of ${entries.length}`}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-0 flex-1 sm:max-w-md">
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              ref={searchRef}
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setSearch("");
              }}
              placeholder="Search name, email or skills — e.g. python react  ( / )"
              aria-label="Search talent pool"
              className={`${inputClass()} pl-9`}
            />
          </div>
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
            aria-label="Sort pool members"
            className={`${inputClass()} w-auto`}
          >
            <option value="fit">Best job fit</option>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name A–Z</option>
          </select>
        </div>

        {jobChips.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
              Open jobs
            </span>
            {jobChips.map((job) => {
              const active = jobFilter === job.id;
              return (
                <button
                  key={job.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setJobFilter(active ? "" : job.id);
                    setSkillFilter([]);
                  }}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition ${
                    active
                      ? "border-navy-600 bg-navy-600 text-white"
                      : "border-zinc-200 bg-white text-zinc-600 hover:border-navy-300 hover:text-navy-700"
                  }`}
                >
                  {job.title}
                  <span className={active ? "text-navy-100" : "text-zinc-400"}>
                    {job.count}
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}

        {topSkills.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
              {jobFilter ? "Job skills" : "Relevant skills"}
            </span>
            {topSkills.map((skill) => {
              const active = skillFilter.includes(skill.key);
              return (
                <button
                  key={skill.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setSkillFilter((prev) =>
                      active
                        ? prev.filter((k) => k !== skill.key)
                        : [...prev, skill.key]
                    )
                  }
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition ${
                    active
                      ? "border-navy-600 bg-navy-600 text-white"
                      : "border-zinc-200 bg-white text-zinc-600 hover:border-navy-300 hover:text-navy-700"
                  }`}
                >
                  {skill.label}
                  <span className={active ? "text-navy-100" : "text-zinc-400"}>
                    {skill.count}
                  </span>
                </button>
              );
            })}
            {skillFilter.length > 0 ? (
              <button
                type="button"
                onClick={() => setSkillFilter([])}
                className="ml-1 text-xs font-medium text-navy-600 hover:underline"
              >
                Clear skills
              </button>
            ) : null}
          </div>
        ) : null}

        {entries.length === 0 ? (
          <EmptyState
            title="Your talent pool is empty"
            description="Candidates you save for future opportunities will appear here."
          />
        ) : visible.length === 0 ? (
          <EmptyState
            title="No one matches your search"
            description="Try a different name, email or skill, or clear the filters."
          >
            <Button
              variant="secondary"
              onClick={() => {
                setSearch("");
                setJobFilter("");
                setSkillFilter([]);
              }}
            >
              Clear search and filters
            </Button>
          </EmptyState>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-navy-50/60 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3">Candidate</th>
                  <th className="px-5 py-3">Contact</th>
                  <th className="px-5 py-3">Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {visible.map((entry) => (
                  <tr key={entry.id} className="hover:bg-navy-50/40">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-100 text-xs font-semibold text-navy-700">
                          {initialsOf(entry.candidate_name)}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-zinc-900">
                            <Highlight
                              text={entry.candidate_name ?? "Pool candidate"}
                              query={search}
                            />
                          </p>
                          {(() => {
                            const matches = entry.matching_jobs ?? [];
                            const shown = jobFilter
                              ? matches.filter((m) => m.job_id === jobFilter)
                              : matches.slice(0, 2);
                            if (shown.length === 0) {
                              return (
                                <p className="mt-1 text-[11px] text-zinc-400">
                                  No skill match for open jobs
                                </p>
                              );
                            }
                            return (
                              <div className="mt-1.5 flex flex-col gap-1.5">
                                {shown.map((match) => (
                                  <div key={match.job_id}>
                                    <p className="text-[11px] font-medium text-zinc-500">
                                      Fits{" "}
                                      <span className="text-zinc-800">
                                        {match.job_title}
                                      </span>
                                    </p>
                                    <div className="mt-0.5 flex flex-wrap gap-1">
                                      {match.matched_skills.slice(0, 6).map((skill) => {
                                        const lower = skill.toLowerCase();
                                        const hit =
                                          skillFilter.includes(lower) ||
                                          terms.some((term) => lower.includes(term));
                                        return (
                                          <span
                                            key={skill}
                                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                              hit
                                                ? "bg-navy-600 text-white"
                                                : "bg-navy-50 text-navy-700"
                                            }`}
                                          >
                                            {skill}
                                          </span>
                                        );
                                      })}
                                      {match.matched_skills.length > 6 ? (
                                        <span
                                          title={match.matched_skills.slice(6).join(", ")}
                                          className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500"
                                        >
                                          +{match.matched_skills.length - 6}
                                        </span>
                                      ) : null}
                                    </div>
                                  </div>
                                ))}
                                {!jobFilter && matches.length > 2 ? (
                                  <p
                                    title={matches
                                      .slice(2)
                                      .map((m) => m.job_title)
                                      .join(", ")}
                                    className="text-[11px] text-zinc-400"
                                  >
                                    +{matches.length - 2} more matching job
                                    {matches.length - 2 === 1 ? "" : "s"}
                                  </p>
                                ) : null}
                              </div>
                            );
                          })()}
                          {entry.source_application_id ? (
                            <Link
                              href={`/dashboard/candidates/${entry.source_application_id}`}
                              className="text-xs text-navy-600 hover:underline"
                            >
                              View application →
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-zinc-600">
                      <p>
                        {entry.candidate_email ? (
                          <a
                            href={`mailto:${entry.candidate_email}`}
                            className="hover:text-navy-700 hover:underline"
                          >
                            <Highlight text={entry.candidate_email} query={search} />
                          </a>
                        ) : (
                          "No email"
                        )}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {entry.consent ? "Consent on file" : "No consent"}
                      </p>
                    </td>
                    <td className="px-5 py-3.5 text-zinc-500">
                      {formatDate(entry.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

    </div>
  );
}
