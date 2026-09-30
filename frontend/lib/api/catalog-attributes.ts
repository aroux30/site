import apiClient from "./client";
import type { ApiPaginationMeta } from "./services";

/**
 * Typed admin client for the product specification sheet: attributes, their
 * values, and tags.  The storefront read path already consumed these tables,
 * but nothing in the admin could write them, so the spec tab and the faceted
 * filters were always empty.  Admin screens go through here rather than
 * calling `apiClient` ad hoc.
 */

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

/** Mirrors the backend `AttributeType` enum (stored by member NAME). */
export type ApiAttributeType = "text" | "number" | "color" | "size";

export interface ApiAttributeValue {
  id: string;
  attribute_id: string;
  value: string;
  slug: string;
  position: number;
}

export interface ApiAttribute {
  id: string;
  name: string;
  slug: string;
  type: ApiAttributeType;
  filterable: boolean;
  position: number;
  values: ApiAttributeValue[];
  created_at: string;
  updated_at: string;
}

export interface ApiAttributeListResponse {
  items: ApiAttribute[];
  meta: ApiPaginationMeta;
}

export interface ApiAttributeValueListResponse {
  items: ApiAttributeValue[];
}

export interface ApiAttributeValueInput {
  value: string;
  slug?: string;
  position?: number;
}

export interface ApiAttributeInput {
  name: string;
  slug?: string;
  type?: ApiAttributeType;
  filterable?: boolean;
  position?: number;
  values?: ApiAttributeValueInput[];
}

/** `values` is create-only: an update never rewrites the value set. */
export type ApiAttributeUpdateInput = Omit<ApiAttributeInput, "values">;

export interface ApiTag {
  id: string;
  name: string;
  slug: string;
}

export interface ApiTagListResponse {
  items: ApiTag[];
  meta: ApiPaginationMeta;
}

/* ------------------------------------------------------------------ */
/*  Attributes                                                        */
/* ------------------------------------------------------------------ */

/**
 * List attributes with their values.  A single request rather than N+1: the
 * editor needs the whole candidate pool to populate its pickers.
 */
export async function fetchAttributes(
  params: { filterable_only?: boolean; page?: number; page_size?: number } = {},
): Promise<ApiAttribute[]> {
  const { data } = await apiClient.get<ApiAttributeListResponse>(
    "/catalog/attributes",
    { params: { page: 1, page_size: 200, ...params } },
  );
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchAttribute(id: string): Promise<ApiAttribute> {
  const { data } = await apiClient.get<ApiAttribute>(`/catalog/attributes/${id}`);
  return data;
}

export async function fetchAttributeValues(
  id: string,
): Promise<ApiAttributeValue[]> {
  const { data } = await apiClient.get<ApiAttributeValueListResponse>(
    `/catalog/attributes/${id}/values`,
  );
  return Array.isArray(data?.items) ? data.items : [];
}

export async function createAttribute(
  payload: ApiAttributeInput,
): Promise<ApiAttribute> {
  const { data } = await apiClient.post<ApiAttribute>("/catalog/attributes", payload);
  return data;
}

export async function updateAttribute(
  id: string,
  payload: ApiAttributeUpdateInput,
): Promise<ApiAttribute> {
  const { data } = await apiClient.patch<ApiAttribute>(
    `/catalog/attributes/${id}`,
    payload,
  );
  return data;
}

/**
 * Delete an attribute.  Refuses with 409 while products still use it, naming
 * how many; `force` accepts the cascade that strips their specification.
 */
export async function deleteAttribute(
  id: string,
  force = false,
): Promise<void> {
  await apiClient.delete(`/catalog/attributes/${id}`, { params: { force } });
}

export async function createAttributeValue(
  attributeId: string,
  payload: ApiAttributeValueInput,
): Promise<ApiAttributeValue> {
  const { data } = await apiClient.post<ApiAttributeValue>(
    `/catalog/attributes/${attributeId}/values`,
    payload,
  );
  return data;
}

export async function deleteAttributeValue(
  attributeId: string,
  valueId: string,
): Promise<void> {
  await apiClient.delete(`/catalog/attributes/${attributeId}/values/${valueId}`);
}

/* ------------------------------------------------------------------ */
/*  Tags                                                              */
/* ------------------------------------------------------------------ */

export async function fetchTags(
  params: { q?: string; page?: number; page_size?: number } = {},
): Promise<ApiTag[]> {
  const { data } = await apiClient.get<ApiTagListResponse>("/catalog/tags", {
    params: { page: 1, page_size: 200, ...params },
  });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function createTag(payload: {
  name: string;
  slug?: string;
}): Promise<ApiTag> {
  const { data } = await apiClient.post<ApiTag>("/catalog/tags", payload);
  return data;
}
