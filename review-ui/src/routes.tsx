import { createBrowserRouter, Navigate } from "react-router";
import { Login } from "./components/login";
import { ReviewQueue } from "./components/review-queue";
import { AdminUsers } from "./components/admin-users";
import { UnitReview } from "./components/unit-review";

export const router = createBrowserRouter([
  { path: "/", Component: Login },
  { path: "/queue", Component: ReviewQueue },
  { path: "/unit/:unitId", Component: UnitReview },
  { path: "/admin/users", Component: AdminUsers },
  { path: "*", element: <Navigate to="/" replace /> },
]);
