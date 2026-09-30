import type { ApiFieldErrors, TripPlanRequest, TripPlanResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiValidationError extends Error {
  fieldErrors: ApiFieldErrors;
  constructor(fieldErrors: ApiFieldErrors) {
    super("Validation failed");
    this.fieldErrors = fieldErrors;
  }
}

export class NetworkError extends Error {}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/trip/health/`);
    if (!response.ok) return false;
    const body = await response.json();
    return body.status === "ok";
  } catch {
    return false;
  }
}

export async function planTrip(request: TripPlanRequest): Promise<TripPlanResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/trip/plan/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch (err) {
    throw new NetworkError(
      "Could not reach the planning service. Check your connection and try again."
    );
  }

  if (response.status === 400 || response.status === 422) {
    const body = (await response.json()) as ApiFieldErrors;
    throw new ApiValidationError(body);
  }

  if (!response.ok) {
    throw new NetworkError(`Trip planning failed (HTTP ${response.status}). Please try again.`);
  }

  return (await response.json()) as TripPlanResponse;
}
