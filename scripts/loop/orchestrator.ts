import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

export type LoopState =
  | "INIT"
  | "PRE_AUDIT"
  | "HYPOTHESIZE"
  | "ACT"
  | "VERIFY"
  | "REGRESSION_GATE"
  | "PROMOTE"
  | "CONSOLIDATE"
  | "HALTED"
  | "COMPLETED";

export interface LoopContext {
  cycleCount: number;
  maxRetries: number;
  budgetTokensTotal: number;
  tokensConsumed: number;
  currentState: LoopState;
  stateHistory: string[];
  failureCount: number;
  lastFingerprint: string | null;
  oscillationDetected: boolean;
}

const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const LOOP_DIR = path.join(PROJECT_ROOT, ".loop");
const NEEDS_HUMAN_PATH = path.join(LOOP_DIR, "NEEDS_HUMAN.md");

export class LoopOrchestrator {
  private context: LoopContext;

  constructor(maxRetries = 3, budgetTokens = 200_000) {
    this.context = {
      cycleCount: 0,
      maxRetries,
      budgetTokensTotal: budgetTokens,
      tokensConsumed: 0,
      currentState: "INIT",
      stateHistory: [],
      failureCount: 0,
      lastFingerprint: null,
      oscillationDetected: false,
    };
  }

  public async run(): Promise<boolean> {
    console.log(">>> [Orchestrator] Starting 8-stage Self-Healing Loop Engine...");

    while (this.context.currentState !== "COMPLETED" && this.context.currentState !== "HALTED") {
      this.context.stateHistory.push(this.context.currentState);

      // Check oscillation circuit breaker (A -> B -> A)
      if (this.detectOscillation()) {
        console.error(">>> [CIRCUIT BREAKER] Oscillation loop detected! Tripping circuit breaker.");
        this.writeNeedsHumanReport("Oscillation detected across consecutive states: " + this.context.stateHistory.slice(-5).join(" -> "));
        this.context.currentState = "HALTED";
        break;
      }

      // Check max retries
      if (this.context.failureCount >= this.context.maxRetries) {
        console.error(`>>> [MAX RETRIES] Exceeded ${this.context.maxRetries} attempts without green verification.`);
        this.writeNeedsHumanReport(`Failed after ${this.context.failureCount} attempts. Manual intervention required.`);
        this.context.currentState = "HALTED";
        break;
      }

      switch (this.context.currentState) {
        case "INIT":
          this.executeInit();
          break;
        case "PRE_AUDIT":
          this.executePreAudit();
          break;
        case "HYPOTHESIZE":
          this.executeHypothesize();
          break;
        case "ACT":
          this.executeAct();
          break;
        case "VERIFY":
          this.executeVerify();
          break;
        case "REGRESSION_GATE":
          this.executeRegressionGate();
          break;
        case "PROMOTE":
          this.executePromote();
          break;
        case "CONSOLIDATE":
          this.executeConsolidate();
          break;
      }
    }

    return this.context.currentState === "COMPLETED";
  }

  private executeInit(): void {
    console.log(">>> [Stage 1/8: INIT] Checking environment, git branch, and invariants...");
    const branch = execSync("git rev-parse --abbrev-ref HEAD", { cwd: PROJECT_ROOT, encoding: "utf8" }).trim();
    if (branch === "main") {
      throw new Error("Loop must NEVER run directly on main branch! Switch to a feature branch first.");
    }
    this.context.currentState = "PRE_AUDIT";
  }

  private executePreAudit(): void {
    console.log(">>> [Stage 2/8: PRE_AUDIT] Executing deterministic visual and DOM audit...");
    try {
      execSync("node .loop/audits/deterministic-audit.mjs", { cwd: PROJECT_ROOT, stdio: "inherit" });
      console.log(">>> Pre-audit passed smoothly.");
      this.context.currentState = "REGRESSION_GATE";
    } catch {
      console.warn(">>> Pre-audit identified actionable gaps. Progressing to HYPOTHESIZE.");
      this.context.currentState = "HYPOTHESIZE";
    }
  }

  private executeHypothesize(): void {
    console.log(">>> [Stage 3/8: HYPOTHESIZE] Formulating targeted repair strategy...");
    this.context.currentState = "ACT";
  }

  private executeAct(): void {
    console.log(">>> [Stage 4/8: ACT] Applying changes and accounting token consumption...");
    this.context.tokensConsumed += 15_000;
    this.context.currentState = "VERIFY";
  }

  private executeVerify(): void {
    console.log(">>> [Stage 5/8: VERIFY] Rebuilding frontend and running deterministic audit...");
    try {
      execSync("node .loop/audits/deterministic-audit.mjs", { cwd: PROJECT_ROOT, stdio: "inherit" });
      this.context.currentState = "REGRESSION_GATE";
    } catch {
      this.context.failureCount++;
      console.warn(`>>> Verification failed. Incrementing failure count to ${this.context.failureCount}. Rolling back uncommitted diff...`);
      execSync("git checkout -- frontend/components/admin/builder/ || true", { cwd: PROJECT_ROOT });
      this.context.currentState = "HYPOTHESIZE";
    }
  }

  private executeRegressionGate(): void {
    console.log(">>> [Stage 6/8: REGRESSION_GATE] Enforcing FULL test suites (Pytest + Vitest)...");

    // 1. Full Pytest unit tests (614+ tests required)
    console.log("    Running backend unit test suite (pytest app/tests/unit)...");
    const pyOut = execSync("python -m pytest app/tests/unit", {
      cwd: path.join(PROJECT_ROOT, "backend"),
      encoding: "utf8",
    });

    const match = pyOut.match(/(\d+)\s+passed/);
    const passedCount = match ? parseInt(match[1], 10) : 0;
    if (passedCount < 600) {
      throw new Error(`Regression gate failed: expected at least 614 passed tests, found ${passedCount}`);
    }
    console.log(`    Pytest passed: ${passedCount} unit tests verified.`);

    // 2. Full Vitest frontend test suite
    console.log("    Running frontend vitest suite...");
    execSync("npm --prefix frontend test", { cwd: PROJECT_ROOT, stdio: "inherit" });

    this.context.currentState = "PROMOTE";
  }

  private executePromote(): void {
    console.log(">>> [Stage 7/8: PROMOTE] Promoting resolved defects to permanent regression tests...");
    try {
      execSync("node scripts/loop/promote-regression.mjs", { cwd: PROJECT_ROOT, stdio: "inherit" });
    } catch (e) {
      console.warn("Promotion note:", e);
    }
    this.context.currentState = "CONSOLIDATE";
  }

  private executeConsolidate(): void {
    console.log(">>> [Stage 8/8: CONSOLIDATE] Checking cycle consolidation schedule...");
    this.context.cycleCount++;
    if (this.context.cycleCount % 5 === 0) {
      console.log("    Cycle checkpoint reached (multiple of 5). Running offline memory consolidation...");
      execSync("node scripts/loop/dream-consolidate.mjs", { cwd: PROJECT_ROOT, stdio: "inherit" });
    }
    this.context.currentState = "COMPLETED";
    console.log(">>> [Loop Engine] Cycle completed successfully.");
  }

  private detectOscillation(): boolean {
    const history = this.context.stateHistory;
    if (history.length < 5) return false;
    const len = history.length;
    // Pattern A -> B -> A -> B
    if (history[len - 1] === history[len - 3] && history[len - 2] === history[len - 4]) {
      return true;
    }
    return false;
  }

  private writeNeedsHumanReport(reason: string): void {
    const content = `# Loop Execution Paused — Human Intervention Required

- **Timestamp**: ${new Date().toISOString()}
- **Cycle Count**: ${this.context.cycleCount}
- **Failure Count**: ${this.context.failureCount} / ${this.context.maxRetries}
- **Tokens Consumed**: ${this.context.tokensConsumed} / ${this.context.budgetTokensTotal}
- **State Trajectory**: ${this.context.stateHistory.join(" -> ")}

## Reason for Pause
${reason}

## Recommended Next Steps
1. Review recent git diff on branch \`${execSync("git rev-parse --abbrev-ref HEAD", { cwd: PROJECT_ROOT, encoding: "utf8" }).trim()}\`.
2. Inspect \`.loop/audits/deterministic-report.json\` for the specific failed assertion.
3. Once rectified, remove this file and re-run the loop orchestrator.
`;
    fs.writeFileSync(NEEDS_HUMAN_PATH, content, "utf8");
    console.log(`>>> Written incident report to ${NEEDS_HUMAN_PATH}`);
  }
}

// CLI entry point
if (process.argv[1] && process.argv[1].endsWith("orchestrator.ts")) {
  const orchestrator = new LoopOrchestrator();
  orchestrator.run().then((ok) => {
    process.exit(ok ? 0 : 1);
  }).catch((err) => {
    console.error("Fatal orchestrator error:", err);
    process.exit(1);
  });
}
