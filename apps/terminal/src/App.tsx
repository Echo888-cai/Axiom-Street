import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import {
  Briefcase,
  ChartCandlestick,
  CirclePlay,
  Database,
  FlaskConical,
  Lightbulb,
  Radio,
  Settings,
} from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { ResearchPage } from "@/pages/research";
import { StrategiesPage } from "@/pages/strategies";
import { StrategyDetailPage } from "@/pages/strategy-detail";
import { BacktestsPage } from "@/pages/backtests";
import { BacktestDetailPage } from "@/pages/backtest-detail";
import { PlaceholderPage } from "@/pages/placeholder";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<ResearchPage />} />
          <Route
            path="market"
            element={
              <PlaceholderPage
                title="Market"
                icon={ChartCandlestick}
                note="Full TradingView-grade charting surface with indicators, compare and watchlist — ships in the next demo slice."
              />
            }
          />
          <Route
            path="ideas"
            element={
              <PlaceholderPage
                title="Ideas"
                icon={Lightbulb}
                note="Research notes and hypothesis tracking, linked to experiments. Every idea keeps its evidence trail."
              />
            }
          />
          <Route path="strategies" element={<StrategiesPage />} />
          <Route path="strategies/:id" element={<StrategyDetailPage />} />
          <Route
            path="experiments"
            element={
              <PlaceholderPage
                title="Experiments"
                icon={FlaskConical}
                note="Multi-version comparison, parameter heatmaps and the trial ledger. The comparison matrix lands in the next slice."
              />
            }
          />
          <Route path="backtests" element={<BacktestsPage />} />
          <Route path="backtests/:id" element={<BacktestDetailPage />} />
          <Route
            path="paper"
            element={
              <PlaceholderPage
                title="Paper Trading"
                icon={CirclePlay}
                note="Simulated execution against live data with full backtest-to-paper reconciliation."
              />
            }
          />
          <Route
            path="live"
            element={
              <PlaceholderPage
                title="Live Trading"
                icon={Radio}
                note="Strategy → Risk → Execution → Broker. Nothing reaches a broker without passing validation gates."
              />
            }
          />
          <Route
            path="portfolio"
            element={
              <PlaceholderPage
                title="Portfolio"
                icon={Briefcase}
                note="Positions, factor exposure, risk contribution and correlation — portfolio analytics in the next slice."
              />
            }
          />
          <Route
            path="data"
            element={
              <PlaceholderPage
                title="Data"
                icon={Database}
                note="Immutable, content-addressed snapshots. Every backtest pins its snapshot ID."
              />
            }
          />
          <Route
            path="settings"
            element={
              <PlaceholderPage
                title="Settings"
                icon={Settings}
                note="Workspace preferences, API keys and engine configuration."
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
