/**
 * Settings-module API clients that had no frontend caller.
 *
 * The backend has carried these endpoints since the WordPress parity pass and
 * nothing in the app called them, which left complete, working features with
 * no way to reach them — a route, a schema and a service that could only be
 * exercised by curl.
 */

import { apiClient } from "./client";

// The admin-email client (adminEmailApi / AdminEmailStatus) was removed on
// 2026-10-07 with the rest of the email feature.

