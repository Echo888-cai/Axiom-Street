import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { NoteFields } from "./note-fields";

it("keeps each chapter's draft when switching the visible editing section", () => {
  function Editor() {
    const [draft, setDraft] = useState({ hypothesis: "初始想法", method: "", conclusion: "", failure_modes: "" });
    return <NoteFields draft={draft} onChange={(key, value) => setDraft((d) => ({ ...d, [key]: value }))} />;
  }
  render(<Editor />);
  fireEvent.change(screen.getByRole("textbox", { name: "研究假设" }), { target: { value: "修改后的想法" } });
  fireEvent.click(screen.getByRole("button", { name: "检验方法" }));
  expect(screen.queryByRole("textbox", { name: "研究假设" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "检验方法" }), { target: { value: "样本外验证" } });
  fireEvent.click(screen.getByRole("button", { name: "研究假设" }));
  expect(screen.getByRole("textbox", { name: "研究假设" })).toHaveValue("修改后的想法");
  fireEvent.click(screen.getByRole("button", { name: "检验方法" }));
  expect(screen.getByRole("textbox", { name: "检验方法" })).toHaveValue("样本外验证");
});
