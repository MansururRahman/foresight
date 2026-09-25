import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TagInput } from "@/components/project/TagInput";

function Harness({ initial = [] as string[] }) {
  const [tags, setTags] = useState<string[]>(initial);
  return (
    <div>
      <TagInput value={tags} onChange={setTags} />
      <output data-testid="tags">{tags.join(",")}</output>
    </div>
  );
}

describe("TagInput", () => {
  it("normalizes new tags to lowercase and trims whitespace on Enter", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByRole("textbox", { name: /add tag/i }), "  Vendor {enter}");
    expect(screen.getByTestId("tags")).toHaveTextContent("vendor");
    expect(screen.getByRole("textbox", { name: /add tag/i })).toHaveValue("");
  });

  it("ignores duplicates and empty input", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["vendor"]} />);
    const box = screen.getByRole("textbox", { name: /add tag/i });
    await user.type(box, "VENDOR{enter}");
    await user.type(box, "   {enter}");
    expect(screen.getByTestId("tags")).toHaveTextContent(/^vendor$/);
    expect(screen.getAllByRole("button", { name: /remove vendor/i })).toHaveLength(1);
  });

  it("adds on comma and removes with the chip button", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const box = screen.getByRole("textbox", { name: /add tag/i });
    await user.type(box, "external,");
    expect(screen.getByTestId("tags")).toHaveTextContent("external");
    await user.click(screen.getByRole("button", { name: /remove external/i }));
    expect(screen.getByTestId("tags")).toHaveTextContent("");
  });
});
