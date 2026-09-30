import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TripForm from "../components/TripForm";

function renderForm(onSubmit = vi.fn()) {
  const utils = render(<TripForm onSubmit={onSubmit} loading={false} backendHealthy={true} />);
  return { onSubmit, ...utils };
}

describe("TripForm", () => {
  it("disables the submit button when current_cycle_used is 70.5 (out of range)", () => {
    renderForm();
    fireEvent.change(screen.getByLabelText(/Current location/i), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/Pickup location/i), { target: { value: "St. Louis, MO" } });
    fireEvent.change(screen.getByLabelText(/Drop-off location/i), { target: { value: "Nashville, TN" } });
    fireEvent.change(screen.getByLabelText(/Current cycle used/i), { target: { value: "70.5" } });

    expect(screen.getByRole("button", { name: /plan trip/i })).toBeDisabled();
  });

  it("enables the submit button when current_cycle_used is exactly 70.0", () => {
    renderForm();
    fireEvent.change(screen.getByLabelText(/Current location/i), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/Pickup location/i), { target: { value: "St. Louis, MO" } });
    fireEvent.change(screen.getByLabelText(/Drop-off location/i), { target: { value: "Nashville, TN" } });
    fireEvent.change(screen.getByLabelText(/Current cycle used/i), { target: { value: "70" } });

    // 70.0 must stay enabled -- the backend, not the frontend, owns the
    // "cycle exhausted" rejection and returns a specific 422 message for
    // it. Blocking it client-side would hide that message from the user.
    expect(screen.getByRole("button", { name: /plan trip/i })).not.toBeDisabled();
  });

  it("shows an inline error and does not call onSubmit when pickup_location is empty", () => {
    const { onSubmit } = renderForm();
    fireEvent.change(screen.getByLabelText(/Current location/i), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/Drop-off location/i), { target: { value: "Nashville, TN" } });
    fireEvent.change(screen.getByLabelText(/Current cycle used/i), { target: { value: "14.5" } });

    fireEvent.click(screen.getByRole("button", { name: /plan trip/i }));

    expect(screen.getByText(/Pickup location is required/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("calls onSubmit with parsed values when the form is valid", () => {
    const { onSubmit } = renderForm();
    fireEvent.change(screen.getByLabelText(/Current location/i), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/Pickup location/i), { target: { value: "St. Louis, MO" } });
    fireEvent.change(screen.getByLabelText(/Drop-off location/i), { target: { value: "Nashville, TN" } });
    fireEvent.change(screen.getByLabelText(/Current cycle used/i), { target: { value: "14.5" } });

    fireEvent.click(screen.getByRole("button", { name: /plan trip/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      current_location: "Chicago, IL",
      pickup_location: "St. Louis, MO",
      dropoff_location: "Nashville, TN",
      current_cycle_used: 14.5,
    });
  });

  it("accepts a value like 69.9 that is not a multiple of the 0.5 spinner step", () => {
    // Regression test: the number input's step=0.5 (for the spinner
    // arrows) also drives the browser's own native constraint
    // validation, which used to block the submit event entirely for
    // any value that isn't a multiple of 0.5 from 0, even though 0-70
    // is the only range this form (and the backend) actually enforces.
    const { onSubmit } = renderForm();
    fireEvent.change(screen.getByLabelText(/Current location/i), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/Pickup location/i), { target: { value: "St. Louis, MO" } });
    fireEvent.change(screen.getByLabelText(/Drop-off location/i), { target: { value: "Nashville, TN" } });
    fireEvent.change(screen.getByLabelText(/Current cycle used/i), { target: { value: "69.9" } });

    fireEvent.click(screen.getByRole("button", { name: /plan trip/i }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ current_cycle_used: 69.9 }));
  });

  it("renders a network error banner when networkError is supplied, without a white screen", () => {
    render(
      <TripForm
        onSubmit={vi.fn()}
        loading={false}
        backendHealthy={false}
        networkError="Could not reach the planning service. Check your connection and try again."
      />
    );
    expect(screen.getByText(/Could not reach the planning service/i)).toBeInTheDocument();
    expect(screen.getByText(/Backend unreachable/i)).toBeInTheDocument();
  });
});
