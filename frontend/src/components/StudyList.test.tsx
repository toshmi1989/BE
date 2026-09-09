import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudyList } from "./StudyList";

vi.mock("../api/client", () => ({
  listStudies: vi.fn(async () => ({
    studies: [
      {
        study_id: "1",
        study_key: "STUDY-A",
        title: "Alpha BE",
        sponsor: "Acme",
        product: "X",
        dose: "10mg",
        lifecycle: "DRAFT",
        status: "ACTIVE",
        readiness: "IN_PROGRESS",
        readiness_label: "In progress",
        document_count: 2,
        created_at: null,
        updated_at: null,
      },
    ],
    total: 1,
    offset: 0,
    limit: 20,
    organization_id: "org",
  })),
}));

describe("StudyList", () => {
  it("renders catalog title and study row", async () => {
    render(<StudyList onOpen={() => undefined} onCreateNew={() => undefined} />);
    expect(await screen.findByText("Мои исследования")).toBeTruthy();
    expect(await screen.findByText("Alpha BE")).toBeTruthy();
    expect(screen.getByText("STUDY-A")).toBeTruthy();
  });
});
