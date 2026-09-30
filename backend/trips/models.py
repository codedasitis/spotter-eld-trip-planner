# This app intentionally has no models.
#
# The trip planner is a pure computation: given a request, it returns a full
# plan. There is nothing worth persisting for this assessment's scope (no
# user accounts, no saved trip history), so there is no ORM dependency
# anywhere in the request path. This keeps `TripPlanner` unit-testable
# without a database and keeps the request/response cycle trivially
# stateless and horizontally scalable.
