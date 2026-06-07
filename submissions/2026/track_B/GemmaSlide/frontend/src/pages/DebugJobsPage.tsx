import { AppTopBar } from "../components/AppTopBar";
import { DebugToolTabs } from "../components/DebugToolTabs";
import { JobsApiInspector } from "../components/JobsApiInspector";

export function DebugJobsPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[1600px] px-4 py-6 md:px-8 md:py-10">
        <AppTopBar
          title="GemmaSlide"
          subtitle="Debug Inspector"
          actionLabel="Back To Main UI"
          actionTo="/"
        />

        <DebugToolTabs />

        <header
          className={`rounded-xl bg-secondary mb-5 overflow-hidden p-6 md:p-8`}
        >
          <div className="relative">
            <p className="text-xs uppercase tracking-[0.24em] text-primary">
              Jobs Queue Debug
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.02em] text-foreground md:text-[2.3rem]">
              Async Jobs API Inspector
            </h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Submit jobs, inspect status/result payloads, and stream live SSE
              events from /api/v1/jobs.
            </p>
          </div>
        </header>

        <JobsApiInspector />
      </div>
    </div>
  );
}
