# Entity Relationship Diagram

## Table of Contents

1. [Overview](#overview)
2. [Core Domain ERD](#core-domain-erd)
3. [Users Module](#users-module)
4. [Products Module](#products-module)
5. [Inventory Module](#inventory-module)
6. [Orders Module](#orders-module)
7. [Payments Module](#payments-module)
8. [Wallet Module](#wallet-module)
9. [Cart Module](#cart-module)
10. [Shipping Module](#shipping-module)
11. [Reviews Module](#reviews-module)
12. [Promotions Module](#promotions-module)
13. [Notifications Module](#notifications-module)
14. [Media Module](#media-module)
15. [CMS Module](#cms-module)
16. [Analytics Module](#analytics-module)
17. [Entity Summary](#entity-summary)

---

## 1. Overview

All entities use **UUID v4** primary keys and include `created_at` and `updated_at` timestamps. The database uses **schema-per-module** isolation in PostgreSQL. Foreign key references across module boundaries are UUID-based without enforced FK constraints to maintain module independence.

**Conventions:**
- `PK` = Primary Key (UUID v4)
- `FK` = Foreign Key
- `UK` = Unique Key
- `IDX` = Indexed
- All monetary values stored as `BIGINT` in Rials (IRR)
- Soft deletes via `deleted_at` timestamp where applicable

---

## 2. Core Domain ERD

This diagram shows the high-level relationships between the primary entities across all modules.

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    USER ||--o{ ADDRESS : has
    USER ||--o| WALLET : owns
    USER ||--o{ REVIEW : writes
    USER ||--o{ CART : has
    USER ||--o{ NOTIFICATION : receives

    PRODUCT ||--o{ PRODUCT_VARIANT : has
    PRODUCT ||--o{ PRODUCT_IMAGE : has
    PRODUCT ||--o{ PRODUCT_ATTRIBUTE : has
    PRODUCT }o--|| CATEGORY : "belongs to"
    PRODUCT }o--o| BRAND : "made by"
    PRODUCT ||--o{ REVIEW : receives
    PRODUCT ||--o{ ORDER_ITEM : "ordered in"

    CATEGORY ||--o{ CATEGORY : "parent of"

    ORDER ||--o{ ORDER_ITEM : contains
    ORDER ||--o{ PAYMENT : "paid via"
    ORDER ||--o| SHIPMENT : "shipped as"
    ORDER ||--o{ ORDER_STATUS_HISTORY : tracks

    PAYMENT ||--o{ PAYMENT_TRANSACTION : records

    WALLET ||--o{ WALLET_TRANSACTION : logs

    CART ||--o{ CART_ITEM : contains

    COUPON ||--o{ COUPON_USAGE : "used in"
```

---

## 3. Users Module

```mermaid
erDiagram
    USER {
        uuid id PK
        string email UK
        string phone UK
        string password_hash
        string first_name
        string last_name
        string display_name
        string avatar_url
        enum role "CUSTOMER | SELLER | ADMIN | SUPER_ADMIN"
        boolean is_active
        boolean is_verified
        boolean is_email_verified
        boolean is_phone_verified
        string mfa_secret
        boolean mfa_enabled
        timestamp last_login_at
        timestamp email_verified_at
        timestamp phone_verified_at
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    ADDRESS {
        uuid id PK
        uuid user_id FK
        string title "e.g. Home, Office"
        string full_name
        string phone
        string province
        string city
        string postal_code
        string street_address
        string unit
        decimal latitude
        decimal longitude
        boolean is_default
        timestamp created_at
        timestamp updated_at
    }

    USER_SESSION {
        uuid id PK
        uuid user_id FK
        string refresh_token UK
        string ip_address
        string user_agent
        string device_type
        boolean is_active
        timestamp expires_at
        timestamp last_activity_at
        timestamp created_at
    }

    ROLE {
        uuid id PK
        string name UK
        string display_name
        string description
        boolean is_system "built-in roles"
        timestamp created_at
    }

    PERMISSION {
        uuid id PK
        string codename UK "e.g. products:write"
        string display_name
        string module
        timestamp created_at
    }

    ROLE_PERMISSION {
        uuid role_id FK
        uuid permission_id FK
    }

    USER ||--o{ ADDRESS : has
    USER ||--o{ USER_SESSION : "logged in via"
    USER }o--|| ROLE : "assigned"
    ROLE ||--o{ ROLE_PERMISSION : has
    PERMISSION ||--o{ ROLE_PERMISSION : "granted to"
```

---

## 4. Products Module

```mermaid
erDiagram
    PRODUCT {
        uuid id PK
        uuid category_id FK
        uuid brand_id FK
        string name
        string slug UK
        string sku UK
        text description
        text short_description
        bigint price "in Rials"
        bigint compare_at_price "original price before discount"
        bigint cost_price "purchase cost"
        enum status "DRAFT | ACTIVE | ARCHIVED"
        boolean is_active
        boolean is_featured
        boolean is_digital
        float weight "in grams"
        jsonb meta_data "flexible attributes"
        string meta_title
        string meta_description
        float avg_rating
        int review_count
        int sold_count
        int view_count
        timestamp published_at
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    CATEGORY {
        uuid id PK
        uuid parent_id FK "self-referencing"
        string name
        string slug UK
        text description
        string image_url
        string icon
        int level
        string path "materialized path e.g. electronics/phones"
        int sort_order
        boolean is_active
        string meta_title
        string meta_description
        timestamp created_at
        timestamp updated_at
    }

    BRAND {
        uuid id PK
        string name UK
        string slug UK
        string name_en
        string logo_url
        text description
        boolean is_active
        int sort_order
        timestamp created_at
        timestamp updated_at
    }

    PRODUCT_VARIANT {
        uuid id PK
        uuid product_id FK
        string name "e.g. Black / 128GB"
        string sku UK
        bigint price "override or same as product"
        bigint compare_at_price
        string color
        string color_hex
        string size
        float weight
        boolean is_active
        int sort_order
        timestamp created_at
        timestamp updated_at
    }

    PRODUCT_IMAGE {
        uuid id PK
        uuid product_id FK
        uuid variant_id FK "nullable, variant-specific image"
        string url
        string alt_text
        int sort_order
        boolean is_primary
        int width
        int height
        timestamp created_at
    }

    PRODUCT_ATTRIBUTE {
        uuid id PK
        uuid product_id FK
        string attribute_name "e.g. Screen Size, RAM"
        string attribute_value "e.g. 6.7 inch, 8GB"
        string attribute_group "e.g. Specifications, General"
        int sort_order
        timestamp created_at
    }

    PRODUCT_TAG {
        uuid product_id FK
        string tag
    }

    PRODUCT ||--o{ PRODUCT_VARIANT : has
    PRODUCT ||--o{ PRODUCT_IMAGE : has
    PRODUCT ||--o{ PRODUCT_ATTRIBUTE : has
    PRODUCT ||--o{ PRODUCT_TAG : tagged
    PRODUCT }o--|| CATEGORY : "belongs to"
    PRODUCT }o--o| BRAND : "made by"
    CATEGORY ||--o{ CATEGORY : "parent of"
    PRODUCT_VARIANT ||--o{ PRODUCT_IMAGE : "has specific"
```

---

## 5. Inventory Module

```mermaid
erDiagram
    STOCK_ITEM {
        uuid id PK
        uuid product_id FK
        uuid variant_id FK "nullable"
        uuid warehouse_id FK
        int quantity "current available stock"
        int reserved_quantity "reserved for pending orders"
        int low_stock_threshold
        boolean track_inventory
        timestamp created_at
        timestamp updated_at
    }

    STOCK_RESERVATION {
        uuid id PK
        uuid stock_item_id FK
        uuid order_id FK
        int quantity
        enum status "PENDING | CONFIRMED | RELEASED | EXPIRED"
        timestamp expires_at
        timestamp created_at
        timestamp updated_at
    }

    STOCK_MOVEMENT {
        uuid id PK
        uuid stock_item_id FK
        uuid reference_id "order_id or adjustment_id"
        enum type "IN | OUT | ADJUSTMENT | RETURN"
        enum reason "PURCHASE | SALE | RETURN | DAMAGED | CORRECTION"
        int quantity_change "positive or negative"
        int quantity_after "stock after movement"
        string notes
        uuid performed_by FK "admin user"
        timestamp created_at
    }

    WAREHOUSE {
        uuid id PK
        string name
        string code UK
        string address
        string city
        string province
        boolean is_active
        boolean is_default
        int priority "for stock allocation"
        timestamp created_at
        timestamp updated_at
    }

    STOCK_ITEM }o--|| WAREHOUSE : "stored in"
    STOCK_ITEM ||--o{ STOCK_RESERVATION : reserves
    STOCK_ITEM ||--o{ STOCK_MOVEMENT : tracks
```

---

## 6. Orders Module

```mermaid
erDiagram
    ORDER {
        uuid id PK
        string order_number UK "human-readable e.g. ORD-20260909-XXXX"
        uuid user_id FK
        uuid shipping_address_id FK
        uuid billing_address_id FK
        enum status "PENDING | CONFIRMED | PROCESSING | SHIPPED | DELIVERED | COMPLETED | CANCELLED | RETURNED"
        bigint subtotal "sum of items"
        bigint shipping_cost
        bigint tax_amount
        bigint discount_amount
        bigint total_amount
        string currency "IRR"
        uuid coupon_id FK "nullable"
        string coupon_code
        text customer_note
        text admin_note
        string ip_address
        string user_agent
        timestamp confirmed_at
        timestamp shipped_at
        timestamp delivered_at
        timestamp completed_at
        timestamp cancelled_at
        string cancellation_reason
        timestamp created_at
        timestamp updated_at
    }

    ORDER_ITEM {
        uuid id PK
        uuid order_id FK
        uuid product_id FK
        uuid variant_id FK "nullable"
        string product_name "snapshot at time of order"
        string variant_name "snapshot"
        string sku "snapshot"
        bigint unit_price "snapshot"
        bigint discount_amount
        int quantity
        bigint total_price "unit_price * quantity - discount"
        string image_url "snapshot"
        jsonb product_snapshot "full product data at order time"
        timestamp created_at
    }

    ORDER_STATUS_HISTORY {
        uuid id PK
        uuid order_id FK
        enum from_status
        enum to_status
        string note
        uuid changed_by FK "nullable, admin user"
        string ip_address
        timestamp created_at
    }

    RETURN_REQUEST {
        uuid id PK
        uuid order_id FK
        uuid order_item_id FK
        uuid user_id FK
        enum status "PENDING | APPROVED | REJECTED | REFUNDED"
        enum reason "DEFECTIVE | WRONG_ITEM | NOT_AS_DESCRIBED | CHANGED_MIND | OTHER"
        text description
        int quantity
        bigint refund_amount
        string admin_response
        uuid reviewed_by FK "admin"
        timestamp reviewed_at
        timestamp created_at
        timestamp updated_at
    }

    ORDER ||--o{ ORDER_ITEM : contains
    ORDER ||--o{ ORDER_STATUS_HISTORY : tracks
    ORDER ||--o{ RETURN_REQUEST : "may have"
    ORDER_ITEM ||--o{ RETURN_REQUEST : "returned from"
```

---

## 7. Payments Module

```mermaid
erDiagram
    PAYMENT {
        uuid id PK
        uuid order_id FK
        uuid user_id FK
        string payment_number UK
        enum gateway "ZARINPAL | MELLAT | SAMAN | PARSIAN | WALLET | COD"
        enum status "PENDING | PROCESSING | COMPLETED | FAILED | REFUNDED | PARTIALLY_REFUNDED"
        bigint amount
        string currency "IRR"
        string gateway_transaction_id "from payment gateway"
        string gateway_reference_id "bank reference number"
        string gateway_card_number "masked card number"
        jsonb gateway_response "full gateway response"
        string callback_url
        timestamp paid_at
        timestamp verified_at
        timestamp created_at
        timestamp updated_at
    }

    PAYMENT_TRANSACTION {
        uuid id PK
        uuid payment_id FK
        enum type "AUTHORIZE | CAPTURE | REFUND | VOID"
        enum status "SUCCESS | FAILED | PENDING"
        bigint amount
        string gateway_transaction_id
        jsonb request_payload
        jsonb response_payload
        string error_code
        string error_message
        string ip_address
        timestamp created_at
    }

    PAYMENT_GATEWAY_CONFIG {
        uuid id PK
        string gateway_name UK
        string display_name
        string merchant_id
        jsonb config "encrypted gateway credentials"
        boolean is_active
        int sort_order
        bigint min_amount
        bigint max_amount
        timestamp created_at
        timestamp updated_at
    }

    REFUND {
        uuid id PK
        uuid payment_id FK
        uuid order_id FK
        uuid return_request_id FK "nullable"
        bigint amount
        enum status "PENDING | PROCESSING | COMPLETED | FAILED"
        string reason
        string gateway_refund_id
        uuid processed_by FK "admin"
        timestamp processed_at
        timestamp created_at
        timestamp updated_at
    }

    PAYMENT ||--o{ PAYMENT_TRANSACTION : records
    PAYMENT ||--o{ REFUND : "refunded via"
```

---

## 8. Wallet Module

```mermaid
erDiagram
    WALLET {
        uuid id PK
        uuid user_id FK UK
        bigint balance "current balance in Rials"
        bigint total_credited "lifetime credits"
        bigint total_debited "lifetime debits"
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    WALLET_TRANSACTION {
        uuid id PK
        uuid wallet_id FK
        enum type "CREDIT | DEBIT"
        enum source "DEPOSIT | CASHBACK | REFUND | PURCHASE | WITHDRAWAL | ADMIN_ADJUSTMENT | TRANSFER_IN | TRANSFER_OUT"
        bigint amount
        bigint balance_after "wallet balance after transaction"
        uuid reference_id "order_id, refund_id, etc."
        string reference_type "ORDER | REFUND | TRANSFER | ADMIN"
        string description
        uuid performed_by FK "nullable, admin for adjustments"
        timestamp created_at
    }

    WALLET_TRANSFER {
        uuid id PK
        uuid from_wallet_id FK
        uuid to_wallet_id FK
        bigint amount
        string description
        enum status "COMPLETED | REVERSED"
        uuid from_transaction_id FK
        uuid to_transaction_id FK
        timestamp created_at
    }

    WALLET ||--o{ WALLET_TRANSACTION : logs
    WALLET ||--o{ WALLET_TRANSFER : "sent from"
    WALLET ||--o{ WALLET_TRANSFER : "received to"
```

---

## 9. Cart Module

```mermaid
erDiagram
    CART {
        uuid id PK
        uuid user_id FK "nullable for guest carts"
        string session_id "for guest identification"
        enum status "ACTIVE | MERGED | CHECKED_OUT | ABANDONED"
        uuid coupon_id FK "nullable"
        string coupon_code
        bigint discount_amount
        string currency "IRR"
        timestamp last_activity_at
        timestamp expires_at
        timestamp created_at
        timestamp updated_at
    }

    CART_ITEM {
        uuid id PK
        uuid cart_id FK
        uuid product_id FK
        uuid variant_id FK "nullable"
        int quantity
        bigint unit_price "price at time of adding"
        bigint total_price
        jsonb product_snapshot "name, image, etc."
        timestamp created_at
        timestamp updated_at
    }

    CART ||--o{ CART_ITEM : contains
```

---

## 10. Shipping Module

```mermaid
erDiagram
    SHIPPING_METHOD {
        uuid id PK
        string name "e.g. Post, Tipax, Express"
        string code UK
        string provider "integration provider"
        text description
        boolean is_active
        int sort_order
        bigint base_cost
        int estimated_days_min
        int estimated_days_max
        boolean is_free_eligible "can be free with conditions"
        bigint free_shipping_threshold "minimum order for free shipping"
        timestamp created_at
        timestamp updated_at
    }

    SHIPPING_ZONE {
        uuid id PK
        string name
        string code UK
        jsonb provinces "list of province codes"
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    SHIPPING_RATE {
        uuid id PK
        uuid shipping_method_id FK
        uuid shipping_zone_id FK
        float min_weight "grams"
        float max_weight "grams"
        bigint rate "cost in Rials"
        timestamp created_at
        timestamp updated_at
    }

    SHIPMENT {
        uuid id PK
        uuid order_id FK UK
        uuid shipping_method_id FK
        string tracking_number
        string tracking_url
        enum status "PENDING | PICKED_UP | IN_TRANSIT | OUT_FOR_DELIVERY | DELIVERED | RETURNED | FAILED"
        bigint shipping_cost
        float total_weight
        string carrier_name
        string carrier_reference
        timestamp estimated_delivery_at
        timestamp shipped_at
        timestamp delivered_at
        timestamp created_at
        timestamp updated_at
    }

    SHIPMENT_TRACKING_EVENT {
        uuid id PK
        uuid shipment_id FK
        enum status
        string location
        string description
        timestamp occurred_at
        timestamp created_at
    }

    SHIPPING_METHOD ||--o{ SHIPPING_RATE : "priced by"
    SHIPPING_ZONE ||--o{ SHIPPING_RATE : "applies to"
    SHIPMENT ||--o{ SHIPMENT_TRACKING_EVENT : tracks
    SHIPPING_METHOD ||--o{ SHIPMENT : "fulfilled via"
```

---

## 11. Reviews Module

```mermaid
erDiagram
    REVIEW {
        uuid id PK
        uuid product_id FK
        uuid user_id FK
        uuid order_id FK "nullable, for verified purchase"
        int rating "1-5"
        string title
        text body
        text pros "comma-separated or JSON"
        text cons "comma-separated or JSON"
        enum status "PENDING | APPROVED | REJECTED"
        boolean is_verified_purchase
        boolean is_recommended
        int helpful_count
        int not_helpful_count
        string rejection_reason
        uuid moderated_by FK "admin"
        timestamp moderated_at
        timestamp created_at
        timestamp updated_at
    }

    REVIEW_VOTE {
        uuid id PK
        uuid review_id FK
        uuid user_id FK
        enum vote "HELPFUL | NOT_HELPFUL"
        timestamp created_at
    }

    REVIEW_REPORT {
        uuid id PK
        uuid review_id FK
        uuid user_id FK
        enum reason "SPAM | INAPPROPRIATE | FAKE | OFFENSIVE | OTHER"
        text description
        enum status "PENDING | REVIEWED | DISMISSED"
        uuid reviewed_by FK "admin"
        timestamp reviewed_at
        timestamp created_at
    }

    REVIEW ||--o{ REVIEW_VOTE : receives
    REVIEW ||--o{ REVIEW_REPORT : "reported via"
```

---

## 12. Promotions Module

```mermaid
erDiagram
    COUPON {
        uuid id PK
        string code UK
        string name
        text description
        enum type "PERCENTAGE | FIXED_AMOUNT | FREE_SHIPPING"
        bigint discount_value "percentage (e.g. 20) or fixed amount in Rials"
        bigint max_discount_amount "cap for percentage discounts"
        bigint min_order_amount "minimum order to apply"
        int usage_limit_total "max total uses"
        int usage_limit_per_user "max uses per user"
        int used_count "current total uses"
        boolean is_active
        boolean is_stackable "can combine with other coupons"
        timestamp starts_at
        timestamp expires_at
        timestamp created_at
        timestamp updated_at
    }

    COUPON_USAGE {
        uuid id PK
        uuid coupon_id FK
        uuid user_id FK
        uuid order_id FK
        bigint discount_applied "actual discount amount"
        timestamp created_at
    }

    DISCOUNT {
        uuid id PK
        uuid campaign_id FK "nullable"
        enum target_type "PRODUCT | CATEGORY | BRAND | ALL"
        uuid target_id FK "product_id, category_id, or brand_id"
        enum type "PERCENTAGE | FIXED_AMOUNT"
        bigint discount_value
        int priority "higher wins if multiple apply"
        boolean is_active
        timestamp starts_at
        timestamp expires_at
        timestamp created_at
        timestamp updated_at
    }

    CAMPAIGN {
        uuid id PK
        string name
        string slug UK
        text description
        string banner_image_url
        enum status "DRAFT | SCHEDULED | ACTIVE | ENDED | CANCELLED"
        timestamp starts_at
        timestamp ends_at
        timestamp created_at
        timestamp updated_at
    }

    COUPON ||--o{ COUPON_USAGE : "used in"
    CAMPAIGN ||--o{ DISCOUNT : includes
```

---

## 13. Notifications Module

```mermaid
erDiagram
    NOTIFICATION {
        uuid id PK
        uuid user_id FK
        enum channel "EMAIL | SMS | PUSH | IN_APP"
        enum type "ORDER_CONFIRMATION | SHIPPING_UPDATE | PAYMENT_RECEIPT | WELCOME | PASSWORD_RESET | PROMOTION | SYSTEM"
        string subject
        text body
        text body_html "for email"
        jsonb metadata "template variables, references"
        boolean is_read
        boolean is_sent
        timestamp read_at
        timestamp sent_at
        timestamp scheduled_at "for delayed sending"
        timestamp created_at
    }

    NOTIFICATION_TEMPLATE {
        uuid id PK
        string name UK
        enum channel "EMAIL | SMS | PUSH"
        string subject_template
        text body_template "with {{variable}} placeholders"
        text body_html_template
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    NOTIFICATION_PREFERENCE {
        uuid id PK
        uuid user_id FK
        enum notification_type
        boolean email_enabled
        boolean sms_enabled
        boolean push_enabled
        boolean in_app_enabled
        timestamp updated_at
    }

    NOTIFICATION_LOG {
        uuid id PK
        uuid notification_id FK
        enum channel
        enum status "QUEUED | SENT | DELIVERED | FAILED | BOUNCED"
        string provider "SMTP | KAVENEGAR | FCM"
        string provider_message_id
        string error_message
        int retry_count
        timestamp sent_at
        timestamp delivered_at
        timestamp created_at
    }

    NOTIFICATION ||--o{ NOTIFICATION_LOG : "delivered via"
```

---

## 14. Media Module

```mermaid
erDiagram
    MEDIA_FILE {
        uuid id PK
        uuid uploaded_by FK
        string original_filename
        string stored_filename "UUID-based name"
        string mime_type
        bigint file_size "bytes"
        string bucket "MinIO bucket name"
        string object_key "full path in bucket"
        string url "public URL"
        enum type "IMAGE | DOCUMENT | VIDEO"
        enum status "UPLOADING | PROCESSING | READY | FAILED"
        jsonb metadata "EXIF, dimensions, etc."
        string alt_text
        string title
        int width "for images"
        int height "for images"
        string blurhash "placeholder hash for images"
        timestamp created_at
        timestamp updated_at
    }

    IMAGE_VARIANT {
        uuid id PK
        uuid media_file_id FK
        enum size "THUMBNAIL | SMALL | MEDIUM | LARGE | ORIGINAL"
        int width
        int height
        string url
        string object_key
        bigint file_size
        string format "webp | avif | jpeg"
        timestamp created_at
    }

    MEDIA_FILE ||--o{ IMAGE_VARIANT : "has sizes"
```

---

## 15. CMS Module

```mermaid
erDiagram
    PAGE {
        uuid id PK
        string title
        string slug UK
        text content "rich text / HTML"
        enum status "DRAFT | PUBLISHED | ARCHIVED"
        string meta_title
        string meta_description
        uuid author_id FK
        int sort_order
        boolean is_in_footer
        boolean is_in_header
        timestamp published_at
        timestamp created_at
        timestamp updated_at
    }

    BANNER {
        uuid id PK
        string title
        string image_url
        string mobile_image_url
        string link_url
        string alt_text
        enum position "HOME_HERO | HOME_SECONDARY | SIDEBAR | CATEGORY_TOP"
        int sort_order
        boolean is_active
        timestamp starts_at
        timestamp ends_at
        timestamp created_at
        timestamp updated_at
    }

    MENU_ITEM {
        uuid id PK
        uuid parent_id FK "self-referencing"
        string label
        string url
        enum menu_location "HEADER | FOOTER | SIDEBAR"
        string icon
        int sort_order
        boolean is_active
        boolean open_in_new_tab
        timestamp created_at
        timestamp updated_at
    }

    FAQ {
        uuid id PK
        string question
        text answer
        string category
        int sort_order
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    SLIDER {
        uuid id PK
        string name
        enum position "HOME | CATEGORY | PRODUCT"
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    SLIDER_ITEM {
        uuid id PK
        uuid slider_id FK
        string title
        string subtitle
        string image_url
        string mobile_image_url
        string link_url
        string button_text
        int sort_order
        boolean is_active
        timestamp starts_at
        timestamp ends_at
        timestamp created_at
        timestamp updated_at
    }

    MENU_ITEM ||--o{ MENU_ITEM : "parent of"
    SLIDER ||--o{ SLIDER_ITEM : contains
```

---

## 16. Analytics Module

```mermaid
erDiagram
    PAGE_VIEW {
        uuid id PK
        uuid user_id FK "nullable for guests"
        string session_id
        string page_url
        string page_type "HOME | PRODUCT | CATEGORY | SEARCH | CHECKOUT"
        uuid reference_id "product_id, category_id, etc."
        string referrer_url
        string utm_source
        string utm_medium
        string utm_campaign
        string ip_address
        string user_agent
        string device_type "MOBILE | TABLET | DESKTOP"
        timestamp created_at
    }

    SALES_METRIC {
        uuid id PK
        date metric_date
        enum period "DAILY | WEEKLY | MONTHLY"
        int total_orders
        int completed_orders
        int cancelled_orders
        int returned_orders
        bigint gross_revenue
        bigint net_revenue
        bigint discount_total
        bigint shipping_revenue
        bigint refund_total
        int new_customers
        int returning_customers
        float average_order_value
        float conversion_rate
        timestamp calculated_at
        timestamp created_at
    }

    PRODUCT_METRIC {
        uuid id PK
        uuid product_id FK
        date metric_date
        int views
        int add_to_cart_count
        int purchase_count
        bigint revenue
        float conversion_rate "views to purchase"
        timestamp created_at
    }

    SEARCH_METRIC {
        uuid id PK
        string query
        int result_count
        int click_count
        float click_through_rate
        int conversion_count
        date metric_date
        timestamp created_at
    }

    ADMIN_AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        string action "CREATE | UPDATE | DELETE | LOGIN | EXPORT"
        string resource_type "PRODUCT | ORDER | USER | SETTING"
        uuid resource_id
        jsonb old_values "before change"
        jsonb new_values "after change"
        string ip_address
        string user_agent
        timestamp created_at
    }
```

---

## 17. Entity Summary

| Module          | Entity                    | Table Name                    | Description                              |
|-----------------|---------------------------|-------------------------------|------------------------------------------|
| **Users**       | User                      | `users.users`                 | Platform users (customers, admins)       |
|                 | Address                   | `users.addresses`             | User delivery/billing addresses          |
|                 | UserSession               | `users.user_sessions`         | Active login sessions                    |
|                 | Role                      | `users.roles`                 | System roles                             |
|                 | Permission                | `users.permissions`           | Granular permissions                     |
|                 | RolePermission            | `users.role_permissions`      | Role-permission mapping                  |
| **Products**    | Product                   | `products.products`           | Product catalog entries                  |
|                 | Category                  | `products.categories`         | Hierarchical product categories          |
|                 | Brand                     | `products.brands`             | Product brands/manufacturers             |
|                 | ProductVariant            | `products.product_variants`   | Size/color/storage variants              |
|                 | ProductImage              | `products.product_images`     | Product photo gallery                    |
|                 | ProductAttribute          | `products.product_attributes` | Dynamic product specifications           |
|                 | ProductTag                | `products.product_tags`       | Searchable tags                          |
| **Inventory**   | StockItem                 | `inventory.stock_items`       | Stock levels per product/warehouse       |
|                 | StockReservation          | `inventory.stock_reservations`| Temporary stock holds                    |
|                 | StockMovement             | `inventory.stock_movements`   | Stock change audit trail                 |
|                 | Warehouse                 | `inventory.warehouses`        | Physical warehouse locations             |
| **Orders**      | Order                     | `orders.orders`               | Customer orders                          |
|                 | OrderItem                 | `orders.order_items`          | Individual items in an order             |
|                 | OrderStatusHistory        | `orders.order_status_history` | Order state change log                   |
|                 | ReturnRequest             | `orders.return_requests`      | Product return/refund requests           |
| **Payments**    | Payment                   | `payments.payments`           | Payment records                          |
|                 | PaymentTransaction        | `payments.payment_transactions`| Gateway transaction log                 |
|                 | PaymentGatewayConfig      | `payments.gateway_configs`    | Payment gateway settings                 |
|                 | Refund                    | `payments.refunds`            | Refund records                           |
| **Wallet**      | Wallet                    | `wallet.wallets`              | User digital wallets                     |
|                 | WalletTransaction         | `wallet.wallet_transactions`  | Wallet credit/debit log                  |
|                 | WalletTransfer            | `wallet.wallet_transfers`     | Wallet-to-wallet transfers               |
| **Cart**        | Cart                      | `cart.carts`                  | Shopping carts                           |
|                 | CartItem                  | `cart.cart_items`              | Items in shopping carts                  |
| **Shipping**    | ShippingMethod            | `shipping.shipping_methods`   | Available shipping providers             |
|                 | ShippingZone              | `shipping.shipping_zones`     | Geographic shipping zones                |
|                 | ShippingRate              | `shipping.shipping_rates`     | Zone/weight-based pricing                |
|                 | Shipment                  | `shipping.shipments`          | Order shipment records                   |
|                 | ShipmentTrackingEvent     | `shipping.tracking_events`    | Shipment status updates                  |
| **Reviews**     | Review                    | `reviews.reviews`             | Product reviews and ratings              |
|                 | ReviewVote                | `reviews.review_votes`        | Helpful/not helpful votes                |
|                 | ReviewReport              | `reviews.review_reports`      | Flagged review reports                   |
| **Promotions**  | Coupon                    | `promotions.coupons`          | Discount coupon codes                    |
|                 | CouponUsage               | `promotions.coupon_usages`    | Coupon redemption records                |
|                 | Discount                  | `promotions.discounts`        | Automatic discount rules                 |
|                 | Campaign                  | `promotions.campaigns`        | Marketing campaigns                      |
| **Notifications**| Notification             | `notifications.notifications` | User notifications                       |
|                 | NotificationTemplate      | `notifications.templates`     | Message templates                        |
|                 | NotificationPreference    | `notifications.preferences`   | User channel preferences                 |
|                 | NotificationLog           | `notifications.logs`          | Delivery status tracking                 |
| **Media**       | MediaFile                 | `media.media_files`           | Uploaded files metadata                  |
|                 | ImageVariant              | `media.image_variants`        | Resized image versions                   |
| **CMS**         | Page                      | `cms.pages`                   | Static content pages                     |
|                 | Banner                    | `cms.banners`                 | Promotional banners                      |
|                 | MenuItem                  | `cms.menu_items`              | Navigation menu entries                  |
|                 | FAQ                       | `cms.faqs`                    | Frequently asked questions               |
|                 | Slider                    | `cms.sliders`                 | Image slider/carousel groups             |
|                 | SliderItem                | `cms.slider_items`            | Individual slider slides                 |
| **Analytics**   | PageView                  | `analytics.page_views`        | Page visit tracking                      |
|                 | SalesMetric               | `analytics.sales_metrics`     | Aggregated sales data                    |
|                 | ProductMetric             | `analytics.product_metrics`   | Per-product performance data             |
|                 | SearchMetric              | `analytics.search_metrics`    | Search query analytics                   |
|                 | AdminAuditLog             | `analytics.admin_audit_logs`  | Admin action audit trail                 |

**Total Entities:** 52

---

*For related documentation, see:*
- *[System Architecture](./system.md)*
- *[Backend Architecture](./backend.md)*
- *[Frontend Architecture](./frontend.md)*
- *[Search Architecture](./search.md)*
