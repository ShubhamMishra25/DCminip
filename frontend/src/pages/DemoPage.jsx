import { useState } from 'react';
import api from '../services/api';

export default function DemoPage() {
  const [numBids, setNumBids] = useState(10);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [selectedTab, setSelectedTab] = useState('with_locks');

  const runSimulation = async (useLocks) => {
    setRunning(true);
    setResults(null);
    try {
      const res = await api.demoRaceCondition(numBids, useLocks);
      setResults({
        ...res,
        mode: useLocks ? 'With Mutual Exclusion (Locks)' : 'Without Synchronization (Race Condition)',
        useLocks,
      });
    } catch (err) {
      setResults({
        success: false,
        report: `Error executing demonstration: ${err.message}`,
        logs: [err.message],
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1>Distributed Computing Concepts Laboratory</h1>
          <p>
            Real-time verification of Mutual Exclusion, Critical Section Atomicity, and Race Conditions
          </p>
        </div>
      </div>

      {/* Explanatory Cards */}
      <div className="dc-concepts-grid mb-8">
        <div className="concept-card">
          <div className="concept-header">
            <span className="concept-icon">🛡️</span>
            <h3>Mutual Exclusion</h3>
          </div>
          <p className="text-sm text-slate-300">
            Guaranteed by <code>threading.Lock</code>. Protects the critical section so that only one worker thread executes the read-validate-update lifecycle at any single instance in time.
          </p>
        </div>

        <div className="concept-card">
          <div className="concept-header">
            <span className="concept-icon">⚡</span>
            <h3>Race Conditions</h3>
          </div>
          <p className="text-sm text-slate-300">
            Without synchronization, multiple concurrent RPC threads read identical stale highest bids. Their updates collide, causing lower bids or inconsistent states to overwrite valid ones.
          </p>
        </div>

        <div className="concept-card">
          <div className="concept-header">
            <span className="concept-icon">🧵</span>
            <h3>ThreadPool Concurrency</h3>
          </div>
          <p className="text-sm text-slate-300">
            The Python gRPC server spawns pooled worker threads for simultaneous client remote procedure calls, logging thread IDs and microsecond timestamps for full traceability.
          </p>
        </div>
      </div>

      {/* Interactive Control Panel */}
      <div className="demo-control-card mb-8">
        <h2 className="text-xl font-bold text-white mb-2">Run Live Concurrency Test</h2>
        <p className="text-sm text-slate-400 mb-6">
          Trigger simultaneous concurrent bidding threads dispatched against the Python server to observe state consistency.
        </p>

        <div className="flex flex-wrap items-center gap-6 mb-6">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-slate-300">Concurrent Bidders:</label>
            <select
              value={numBids}
              onChange={(e) => setNumBids(parseInt(e.target.value))}
              disabled={running}
              className="bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="5">5 Threads</option>
              <option value="10">10 Threads</option>
              <option value="20">20 Threads</option>
            </select>
          </div>

          <div className="flex gap-4">
            <button
              onClick={() => runSimulation(false)}
              disabled={running}
              className="btn btn-danger flex items-center gap-2"
            >
              <span>⚠️</span>
              {running ? 'Running Test...' : 'Run WITHOUT Synchronization'}
            </button>

            <button
              onClick={() => runSimulation(true)}
              disabled={running}
              className="btn btn-primary flex items-center gap-2"
            >
              <span>🔒</span>
              {running ? 'Running Test...' : 'Run WITH Synchronization (Locks)'}
            </button>
          </div>
        </div>

        {running && (
          <div className="flex items-center gap-3 py-4 text-indigo-400 animate-pulse text-sm">
            <div className="loading-spinner"></div>
            <span>Dispatching concurrent threads and barrier synchronization in backend...</span>
          </div>
        )}
      </div>

      {/* Results Section */}
      {results && (
        <div className="demo-results-card">
          <div className="flex-between mb-4 border-b border-slate-700 pb-3">
            <div>
              <h3 className="text-xl font-bold text-white">{results.mode}</h3>
              <p className="text-xs text-slate-400">
                Processed {numBids} concurrent requests with thread barriers
              </p>
            </div>
            <div>
              <span
                className={`text-sm px-3 py-1 rounded-full font-bold ${
                  results.race_condition_detected
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                }`}
              >
                {results.race_condition_detected ? '⚠️ RACE CONDITION DETECTED' : '✓ MUTUAL EXCLUSION VERIFIED'}
              </span>
            </div>
          </div>

          {/* Metric Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="stat-card">
              <span className="stat-card-label">Expected Highest Bid</span>
              <span className="stat-card-value font-mono text-indigo-300">
                ${results.expected_highest_bid?.toFixed(2)}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-card-label">Actual Final Bid</span>
              <span className={`stat-card-value font-mono ${results.race_condition_detected ? 'text-rose-400' : 'text-emerald-400'}`}>
                ${results.actual_highest_bid?.toFixed(2)}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-card-label">Integrity Status</span>
              <span className="text-sm font-semibold mt-2">
                {results.race_condition_detected
                  ? 'Inconsistent / Overwritten State'
                  : '100% Consistent & Atomic'}
              </span>
            </div>
          </div>

          {/* Terminal Logs */}
          <div className="terminal-window">
            <div className="terminal-header">
              <span className="terminal-dot bg-rose-500"></span>
              <span className="terminal-dot bg-amber-500"></span>
              <span className="terminal-dot bg-emerald-500"></span>
              <span className="terminal-title">Thread Execution Logs & RPC Traces</span>
            </div>
            <pre className="terminal-body">
              {results.logs && results.logs.length > 0
                ? results.logs.join('\n')
                : results.report || 'No log output'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
