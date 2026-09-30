# Search Architecture

## Table of Contents

1. [Overview](#overview)
2. [Elasticsearch Configuration](#elasticsearch-configuration)
3. [Persian Language Analysis](#persian-language-analysis)
4. [Index Design](#index-design)
5. [Search Features](#search-features)
6. [Autocomplete and Suggestions](#autocomplete-and-suggestions)
7. [Faceted Search](#faceted-search)
8. [Indexing Pipeline](#indexing-pipeline)
9. [Query Architecture](#query-architecture)
10. [Performance Optimization](#performance-optimization)
11. [Monitoring and Analytics](#monitoring-and-analytics)

---

## 1. Overview

The search system is powered by **Elasticsearch 8** with custom Persian language analysis. It provides full-text search, faceted filtering, autocomplete suggestions, and search analytics for the e-commerce platform. The architecture is designed to handle Persian text with its unique challenges including character normalization, stemming, and right-to-left text processing.

### Key Capabilities

- Full-text search with Persian language support
- Character normalization (Arabic-to-Persian mapping)
- Persian stemming and lemmatization
- Synonym expansion for product terms
- Faceted search with dynamic filters
- Autocomplete with query suggestions
- Typo tolerance and fuzzy matching
- Search result boosting and relevance tuning
- Search analytics and trending queries

---

## 2. Elasticsearch Configuration

### 2.1 Cluster Setup

```yaml
# elasticsearch.yml

cluster.name: ecommerce-search
node.name: es-node-01

network.host: 0.0.0.0
http.port: 9200
transport.port: 9300

discovery.type: single-node        # Single node for Phase 1

# Security
xpack.security.enabled: true
xpack.security.http.ssl.enabled: false     # SSL handled by Nginx

# Memory
indices.memory.index_buffer_size: 30%
indices.queries.cache.size: 20%

# Thread pool
thread_pool.search.size: 8
thread_pool.search.queue_size: 1000
thread_pool.write.size: 4
thread_pool.write.queue_size: 200
```

### 2.2 JVM Configuration

```
# jvm.options

-Xms2g
-Xmx2g

# GC settings
-XX:+UseG1GC
-XX:G1HeapRegionSize=16m
-XX:InitiatingHeapOccupancyPercent=75
```

---

## 3. Persian Language Analysis

### 3.1 Analysis Chain Overview

```
Input Text
    │
    ▼
┌──────────────────────────────────┐
│        Character Filters          │
│                                    │
│  1. arabic_to_persian_char_filter │   ك → ک, ي → ی, ة → ه
│  2. zero_width_non_joiner         │   Remove ZWNJ / normalize
│  3. half_space_normalizer          │   Normalize half-spaces
│  4. digit_normalizer               │   ۰-۹ → 0-9
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│          Tokenizer                │
│                                    │
│  standard tokenizer               │   Split on whitespace/punctuation
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│        Token Filters              │
│                                    │
│  1. lowercase                      │   Normalize case
│  2. persian_stop                   │   Remove Persian stop words
│  3. persian_normalization          │   ES built-in Persian normalizer
│  4. arabic_normalization           │   Handle Arabic script variants
│  5. persian_stemmer                │   Stem Persian words
│  6. synonym_filter                 │   Expand synonyms
│  7. asciifolding                   │   Fallback ASCII mapping
└──────────────┬───────────────────┘
               │
               ▼
        Indexed Tokens
```

### 3.2 Custom Analyzer Definition

```json
{
  "settings": {
    "analysis": {
      "char_filter": {
        "arabic_to_persian": {
          "type": "mapping",
          "mappings": [
            "\\u0643=>\\u06A9",
            "\\u064A=>\\u06CC",
            "\\u0649=>\\u06CC",
            "\\u0629=>\\u0647",
            "\\u0624=>\\u0648",
            "\\u0623=>\\u0627",
            "\\u0625=>\\u0627",
            "\\u0622=>\\u0627",
            "\\u0671=>\\u0627"
          ]
        },
        "zero_width_char_filter": {
          "type": "mapping",
          "mappings": [
            "\\u200C=> ",
            "\\u200D=>",
            "\\u200B=>",
            "\\uFEFF=>"
          ]
        },
        "digit_normalizer": {
          "type": "mapping",
          "mappings": [
            "\\u06F0=>0", "\\u06F1=>1", "\\u06F2=>2",
            "\\u06F3=>3", "\\u06F4=>4", "\\u06F5=>5",
            "\\u06F6=>6", "\\u06F7=>7", "\\u06F8=>8",
            "\\u06F9=>9",
            "\\u0660=>0", "\\u0661=>1", "\\u0662=>2",
            "\\u0663=>3", "\\u0664=>4", "\\u0665=>5",
            "\\u0666=>6", "\\u0667=>7", "\\u0668=>8",
            "\\u0669=>9"
          ]
        }
      },
      "filter": {
        "persian_stop": {
          "type": "stop",
          "stopwords": "_persian_"
        },
        "persian_custom_stop": {
          "type": "stop",
          "stopwords": [
            "و", "در", "به", "از", "که", "این", "را",
            "با", "است", "برای", "آن", "یک", "خود",
            "تا", "کرد", "بر", "هم", "نیز", "گفت",
            "می", "شد", "هر", "یا", "اما", "باید"
          ]
        },
        "persian_stemmer": {
          "type": "stemmer",
          "language": "arabic"
        },
        "product_synonyms": {
          "type": "synonym_graph",
          "synonyms_path": "analysis/synonyms_fa.txt",
          "updateable": true
        },
        "autocomplete_filter": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 15
        }
      },
      "analyzer": {
        "persian_custom": {
          "type": "custom",
          "char_filter": [
            "arabic_to_persian",
            "zero_width_char_filter",
            "digit_normalizer"
          ],
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "persian_normalization",
            "arabic_normalization",
            "persian_stop",
            "persian_custom_stop",
            "persian_stemmer",
            "product_synonyms"
          ]
        },
        "persian_autocomplete": {
          "type": "custom",
          "char_filter": [
            "arabic_to_persian",
            "zero_width_char_filter",
            "digit_normalizer"
          ],
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "persian_normalization",
            "arabic_normalization",
            "autocomplete_filter"
          ]
        },
        "persian_search": {
          "type": "custom",
          "char_filter": [
            "arabic_to_persian",
            "zero_width_char_filter",
            "digit_normalizer"
          ],
          "tokenizer": "standard",
          "filter": [
            "lowercase",
            "persian_normalization",
            "arabic_normalization",
            "persian_stop",
            "persian_custom_stop",
            "persian_stemmer",
            "product_synonyms"
          ]
        }
      }
    }
  }
}
```

### 3.3 Synonym Dictionary

The synonym file (`analysis/synonyms_fa.txt`) maps equivalent terms in the Iranian e-commerce context:

```
# Electronics
موبایل, گوشی, تلفن همراه, گوشی موبایل
لپتاپ, لپ تاپ, نوت بوک, نوتبوک, لب تاب
تبلت, تب لت, tablet
هدفون, هندزفری, هنذفری, هدست, هدفن
پاوربانک, شارژر همراه, پاور بانک

# Clothing
تیشرت, تی شرت, t-shirt
شلوار جین, شلوار لی, جین
کفش ورزشی, کتونی, کتانی, اسنیکر
مانتو, مانتوی

# Home
یخچال, یخچال فریزر
لباسشویی, ماشین لباسشویی, لباس شویی
جاروبرقی, جارو برقی, جاروبرقی

# Common misspellings and variations
سامسونگ, samsung, سامسونق
اپل, apple, آیفون, iphone
شیائومی, xiaomi, شیاومی, شیامی
```

### 3.4 Character Normalization Examples

| Input                    | After Normalization  | Explanation                        |
|--------------------------|---------------------|------------------------------------|
| `كتاب`                  | `کتاب`              | Arabic Kaf → Persian Kaf           |
| `موبايل`                | `موبایل`            | Arabic Yaa → Persian Yaa           |
| `١٢٣٤`                  | `1234`              | Arabic digits → ASCII digits       |
| `۱۲۳۴`                  | `1234`              | Persian digits → ASCII digits      |
| `می‌خواهم` (with ZWNJ)  | `می خواهم`          | ZWNJ replaced with space           |

---

## 4. Index Design

### 4.1 Products Index

```json
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "name": {
        "type": "text",
        "analyzer": "persian_custom",
        "search_analyzer": "persian_search",
        "fields": {
          "exact": { "type": "keyword" },
          "autocomplete": {
            "type": "text",
            "analyzer": "persian_autocomplete",
            "search_analyzer": "persian_search"
          },
          "english": {
            "type": "text",
            "analyzer": "english"
          }
        }
      },
      "description": {
        "type": "text",
        "analyzer": "persian_custom",
        "search_analyzer": "persian_search"
      },
      "slug": { "type": "keyword" },
      "sku": { "type": "keyword" },
      "brand": {
        "properties": {
          "id": { "type": "keyword" },
          "name": {
            "type": "text",
            "analyzer": "persian_custom",
            "fields": {
              "keyword": { "type": "keyword" }
            }
          }
        }
      },
      "category": {
        "properties": {
          "id": { "type": "keyword" },
          "name": { "type": "keyword" },
          "path": { "type": "keyword" },
          "breadcrumb": {
            "type": "text",
            "analyzer": "persian_custom"
          }
        }
      },
      "price": {
        "properties": {
          "amount": { "type": "long" },
          "discounted_amount": { "type": "long" },
          "currency": { "type": "keyword" },
          "discount_percent": { "type": "float" }
        }
      },
      "attributes": {
        "type": "nested",
        "properties": {
          "name": { "type": "keyword" },
          "value": { "type": "keyword" },
          "value_text": {
            "type": "text",
            "analyzer": "persian_custom"
          }
        }
      },
      "variants": {
        "type": "nested",
        "properties": {
          "id": { "type": "keyword" },
          "name": { "type": "keyword" },
          "sku": { "type": "keyword" },
          "price": { "type": "long" },
          "in_stock": { "type": "boolean" },
          "color": { "type": "keyword" },
          "size": { "type": "keyword" }
        }
      },
      "images": {
        "properties": {
          "url": { "type": "keyword", "index": false },
          "alt": { "type": "text", "analyzer": "persian_custom" }
        }
      },
      "rating": {
        "properties": {
          "average": { "type": "float" },
          "count": { "type": "integer" }
        }
      },
      "tags": { "type": "keyword" },
      "in_stock": { "type": "boolean" },
      "is_active": { "type": "boolean" },
      "sold_count": { "type": "integer" },
      "view_count": { "type": "integer" },
      "created_at": { "type": "date" },
      "updated_at": { "type": "date" },
      "suggest": {
        "type": "completion",
        "analyzer": "persian_custom",
        "preserve_separators": true,
        "preserve_position_increments": true,
        "max_input_length": 50
      }
    }
  }
}
```

### 4.2 Categories Index

```json
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "name": {
        "type": "text",
        "analyzer": "persian_custom",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "slug": { "type": "keyword" },
      "parent_id": { "type": "keyword" },
      "path": { "type": "keyword" },
      "level": { "type": "integer" },
      "product_count": { "type": "integer" },
      "is_active": { "type": "boolean" },
      "sort_order": { "type": "integer" },
      "suggest": {
        "type": "completion",
        "analyzer": "persian_custom"
      }
    }
  }
}
```

### 4.3 Search Suggestions Index

```json
{
  "mappings": {
    "properties": {
      "query": {
        "type": "text",
        "analyzer": "persian_custom",
        "fields": {
          "autocomplete": {
            "type": "text",
            "analyzer": "persian_autocomplete",
            "search_analyzer": "persian_search"
          },
          "keyword": { "type": "keyword" }
        }
      },
      "frequency": { "type": "integer" },
      "result_count": { "type": "integer" },
      "last_searched": { "type": "date" },
      "is_trending": { "type": "boolean" }
    }
  }
}
```

---

## 5. Search Features

### 5.1 Full-Text Search

The primary search query uses a multi-match approach with field boosting:

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "گوشی سامسونگ",
            "type": "best_fields",
            "fields": [
              "name^5",
              "name.english^3",
              "brand.name^4",
              "category.breadcrumb^2",
              "description",
              "tags^2",
              "attributes.value_text"
            ],
            "fuzziness": "AUTO",
            "prefix_length": 2,
            "minimum_should_match": "75%"
          }
        }
      ],
      "filter": [
        { "term": { "is_active": true } },
        { "term": { "in_stock": true } }
      ],
      "should": [
        {
          "range": {
            "rating.average": {
              "gte": 4.0,
              "boost": 1.5
            }
          }
        },
        {
          "range": {
            "sold_count": {
              "gte": 100,
              "boost": 1.2
            }
          }
        }
      ]
    }
  }
}
```

### 5.2 Field Boosting Strategy

| Field                  | Boost | Rationale                                 |
|------------------------|-------|-------------------------------------------|
| `name`                 | 5.0   | Primary search target                     |
| `brand.name`           | 4.0   | Brand searches are high-intent            |
| `name.english`         | 3.0   | English brand/product names               |
| `category.breadcrumb`  | 2.0   | Category context for relevance            |
| `tags`                 | 2.0   | Curated keywords                          |
| `description`          | 1.0   | Broad context match                       |
| `attributes.value_text`| 1.0   | Attribute-based search                    |

### 5.3 Fuzzy Matching

Fuzzy matching handles common Persian typing mistakes:

```json
{
  "fuzziness": "AUTO",
  "prefix_length": 2,
  "max_expansions": 50,
  "fuzzy_transpositions": true
}
```

`AUTO` fuzziness rules:
- 0-2 characters: exact match required
- 3-5 characters: 1 edit distance allowed
- 6+ characters: 2 edit distances allowed

---

## 6. Autocomplete and Suggestions

### 6.1 Autocomplete Architecture

```
User Types "گوش"
    │
    ▼
┌──────────────────────────────────────────────┐
│              Autocomplete Pipeline            │
│                                                │
│  1. Query Suggestions (from search history)   │
│     "گوشی سامسونگ"                            │
│     "گوشی آیفون"                               │
│     "گوشواره طلا"                              │
│                                                │
│  2. Product Suggestions (from product index)  │
│     { name: "گوشی Samsung Galaxy S24", ... }  │
│     { name: "گوشی iPhone 15 Pro", ... }       │
│                                                │
│  3. Category Suggestions                       │
│     "گوشی موبایل" (category)                   │
│     "گوشواره و زیورآلات" (category)             │
│                                                │
│  Combined and ranked by relevance + popularity │
└──────────────────────────────────────────────┘
```

### 6.2 Autocomplete Query

```json
{
  "suggest": {
    "product-suggest": {
      "prefix": "گوش",
      "completion": {
        "field": "suggest",
        "size": 5,
        "skip_duplicates": true,
        "fuzzy": {
          "fuzziness": 1
        }
      }
    }
  },
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "name.autocomplete": {
              "query": "گوش",
              "operator": "and"
            }
          }
        }
      ],
      "filter": [
        { "term": { "is_active": true } }
      ]
    }
  },
  "size": 5,
  "_source": ["id", "name", "slug", "price", "images"]
}
```

### 6.3 Trending Searches

Trending searches are tracked and displayed to users without a query:

```python
# Update search frequency on each search
async def track_search_query(query: str, result_count: int):
    await es.update(
        index="search_suggestions",
        id=hashlib.md5(query.encode()).hexdigest(),
        body={
            "script": {
                "source": """
                    ctx._source.frequency += 1;
                    ctx._source.last_searched = params.now;
                    ctx._source.result_count = params.result_count;
                """,
                "params": {
                    "now": datetime.utcnow().isoformat(),
                    "result_count": result_count,
                },
            },
            "upsert": {
                "query": query,
                "frequency": 1,
                "result_count": result_count,
                "last_searched": datetime.utcnow().isoformat(),
                "is_trending": False,
            },
        },
    )
```

---

## 7. Faceted Search

### 7.1 Facet Types

| Facet Type        | Implementation         | Example                          |
|-------------------|------------------------|----------------------------------|
| **Category**      | Terms aggregation       | موبایل (120), لپتاپ (85)         |
| **Brand**         | Terms aggregation       | سامسونگ (45), اپل (38)           |
| **Price Range**   | Range aggregation       | زیر ۱ میلیون, ۱-۵ میلیون         |
| **Rating**        | Range aggregation       | ۴ ستاره و بالاتر                 |
| **Color**         | Nested terms agg        | مشکی (30), سفید (25)            |
| **Size**          | Nested terms agg        | S, M, L, XL                      |
| **Availability**  | Filter aggregation      | موجود (200), ناموجود (50)        |
| **Discount**      | Filter aggregation      | تخفیف‌دار (75)                   |
| **Dynamic Attrs** | Nested aggregation      | Category-specific attributes     |

### 7.2 Aggregation Query

```json
{
  "aggs": {
    "categories": {
      "terms": {
        "field": "category.name",
        "size": 20,
        "order": { "_count": "desc" }
      }
    },
    "brands": {
      "terms": {
        "field": "brand.name.keyword",
        "size": 30,
        "order": { "_count": "desc" }
      }
    },
    "price_ranges": {
      "range": {
        "field": "price.amount",
        "ranges": [
          { "key": "under_1m", "to": 10000000 },
          { "key": "1m_5m", "from": 10000000, "to": 50000000 },
          { "key": "5m_10m", "from": 50000000, "to": 100000000 },
          { "key": "10m_20m", "from": 100000000, "to": 200000000 },
          { "key": "above_20m", "from": 200000000 }
        ]
      }
    },
    "price_stats": {
      "stats": {
        "field": "price.amount"
      }
    },
    "ratings": {
      "range": {
        "field": "rating.average",
        "ranges": [
          { "key": "4_and_above", "from": 4.0 },
          { "key": "3_and_above", "from": 3.0 },
          { "key": "2_and_above", "from": 2.0 }
        ]
      }
    },
    "colors": {
      "nested": {
        "path": "variants"
      },
      "aggs": {
        "color_values": {
          "terms": {
            "field": "variants.color",
            "size": 20
          }
        }
      }
    },
    "availability": {
      "filters": {
        "filters": {
          "in_stock": { "term": { "in_stock": true } },
          "out_of_stock": { "term": { "in_stock": false } }
        }
      }
    },
    "has_discount": {
      "filter": {
        "range": {
          "price.discount_percent": { "gt": 0 }
        }
      }
    },
    "dynamic_attributes": {
      "nested": {
        "path": "attributes"
      },
      "aggs": {
        "attribute_names": {
          "terms": {
            "field": "attributes.name",
            "size": 20
          },
          "aggs": {
            "attribute_values": {
              "terms": {
                "field": "attributes.value",
                "size": 30
              }
            }
          }
        }
      }
    }
  }
}
```

### 7.3 Facet Response Structure

```json
{
  "facets": {
    "categories": [
      { "key": "گوشی موبایل", "count": 120 },
      { "key": "تبلت", "count": 45 },
      { "key": "لوازم جانبی", "count": 200 }
    ],
    "brands": [
      { "key": "سامسونگ", "count": 85 },
      { "key": "اپل", "count": 62 },
      { "key": "شیائومی", "count": 48 }
    ],
    "price_ranges": [
      { "key": "under_1m", "label": "زیر ۱ میلیون", "count": 150 },
      { "key": "1m_5m", "label": "۱ تا ۵ میلیون", "count": 200 },
      { "key": "5m_10m", "label": "۵ تا ۱۰ میلیون", "count": 100 }
    ],
    "attributes": {
      "رنگ": [
        { "key": "مشکی", "count": 95 },
        { "key": "سفید", "count": 72 }
      ],
      "حافظه داخلی": [
        { "key": "128GB", "count": 60 },
        { "key": "256GB", "count": 45 }
      ]
    }
  }
}
```

---

## 8. Indexing Pipeline

### 8.1 Indexing Strategy

```
┌──────────────────────────────────────────────────────────┐
│                  Indexing Pipeline                         │
│                                                            │
│  Trigger Events:                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Product CRUD │  │ Price Change │  │ Stock Update   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │            │
│         └────────┬───────┴───────────────────┘            │
│                  │                                        │
│                  ▼                                        │
│         ┌────────────────┐                                │
│         │  Domain Event  │                                │
│         └───────┬────────┘                                │
│                 │                                         │
│                 ▼                                         │
│         ┌────────────────┐                                │
│         │  Celery Task   │  (async, with retry)          │
│         └───────┬────────┘                                │
│                 │                                         │
│                 ▼                                         │
│    ┌────────────────────────┐                             │
│    │  Build Index Document  │  (fetch from PostgreSQL)   │
│    └───────────┬────────────┘                             │
│                │                                          │
│                ▼                                          │
│    ┌────────────────────────┐                             │
│    │  Elasticsearch Index   │  (upsert / delete)         │
│    └────────────────────────┘                             │
│                                                            │
│  Full Reindex:                                            │
│  ┌────────────────┐     ┌──────────────────────────────┐ │
│  │ Management CMD │────▶│ Create new index with alias  │ │
│  └────────────────┘     │ Bulk index all products      │ │
│                          │ Swap alias atomically        │ │
│                          │ Delete old index             │ │
│                          └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 8.2 Real-Time Indexing (Celery Task)

```python
# app/tasks/search_tasks.py

from celery import shared_task
from app.core.elasticsearch import get_es_client
from app.modules.products.infrastructure.repository import SQLAlchemyProductRepository

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def index_product(self, product_id: str):
    """Index or update a single product in Elasticsearch."""
    es = get_es_client()
    repo = SQLAlchemyProductRepository(get_session())

    product = repo.find_by_id(product_id)
    if not product:
        # Product was deleted, remove from index
        es.delete(index="products", id=product_id, ignore=[404])
        return

    document = build_product_document(product)
    es.index(index="products", id=product_id, document=document)


@shared_task
def bulk_reindex_products():
    """Full reindex of all products using index aliasing."""
    es = get_es_client()
    new_index = f"products_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Create new index with mappings
    es.indices.create(index=new_index, body=PRODUCT_INDEX_SETTINGS)

    # Bulk index all products
    repo = SQLAlchemyProductRepository(get_session())
    products = repo.find_all_active()

    actions = [
        {
            "_index": new_index,
            "_id": str(product.id),
            "_source": build_product_document(product),
        }
        for product in products
    ]

    helpers.bulk(es, actions, chunk_size=500)

    # Swap alias atomically
    es.indices.update_aliases(body={
        "actions": [
            {"remove": {"index": "products_*", "alias": "products"}},
            {"add": {"index": new_index, "alias": "products"}},
        ]
    })

    # Clean up old indices
    cleanup_old_indices(es, "products_", keep=2)
```

### 8.3 Document Builder

```python
def build_product_document(product: Product) -> dict:
    """Build an Elasticsearch document from a Product entity."""
    return {
        "id": str(product.id),
        "name": product.name,
        "description": product.description,
        "slug": product.slug,
        "sku": product.sku,
        "brand": {
            "id": str(product.brand.id) if product.brand else None,
            "name": product.brand.name if product.brand else None,
        },
        "category": {
            "id": str(product.category.id),
            "name": product.category.name,
            "path": product.category.path,
            "breadcrumb": " > ".join(product.category.breadcrumb),
        },
        "price": {
            "amount": product.price,
            "discounted_amount": product.discounted_price,
            "currency": "IRR",
            "discount_percent": product.discount_percent,
        },
        "attributes": [
            {
                "name": attr.name,
                "value": attr.value,
                "value_text": attr.value,
            }
            for attr in product.attributes
        ],
        "variants": [
            {
                "id": str(v.id),
                "name": v.name,
                "sku": v.sku,
                "price": v.price,
                "in_stock": v.stock > 0,
                "color": v.color,
                "size": v.size,
            }
            for v in product.variants
        ],
        "images": [
            {"url": img.url, "alt": img.alt}
            for img in product.images
        ],
        "rating": {
            "average": product.avg_rating,
            "count": product.review_count,
        },
        "tags": product.tags,
        "in_stock": product.total_stock > 0,
        "is_active": product.is_active,
        "sold_count": product.sold_count,
        "view_count": product.view_count,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
        "suggest": {
            "input": [
                product.name,
                product.brand.name if product.brand else "",
                *product.tags,
            ],
            "weight": product.sold_count + product.view_count,
        },
    }
```

---

## 9. Query Architecture

### 9.1 Search Service

```python
# app/modules/search/application/services.py

class SearchService:
    def __init__(self, es_client: Elasticsearch):
        self._es = es_client

    async def search_products(self, params: SearchParams) -> SearchResult:
        query = self._build_query(params)
        response = await self._es.search(
            index="products",
            body=query,
            request_timeout=5,
        )
        return self._parse_response(response, params)

    def _build_query(self, params: SearchParams) -> dict:
        must = []
        filter_clauses = [
            {"term": {"is_active": True}},
        ]

        # Text search
        if params.query:
            must.append({
                "multi_match": {
                    "query": params.query,
                    "type": "best_fields",
                    "fields": [
                        "name^5", "name.english^3", "brand.name^4",
                        "category.breadcrumb^2", "description", "tags^2",
                    ],
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                    "minimum_should_match": "75%",
                }
            })

        # Filters
        if params.category_id:
            filter_clauses.append({"term": {"category.id": params.category_id}})
        if params.brand_ids:
            filter_clauses.append({"terms": {"brand.id": params.brand_ids}})
        if params.in_stock_only:
            filter_clauses.append({"term": {"in_stock": True}})
        if params.min_price or params.max_price:
            price_range = {}
            if params.min_price:
                price_range["gte"] = params.min_price
            if params.max_price:
                price_range["lte"] = params.max_price
            filter_clauses.append({"range": {"price.amount": price_range}})
        if params.min_rating:
            filter_clauses.append({"range": {"rating.average": {"gte": params.min_rating}}})

        # Sorting
        sort = self._build_sort(params.sort_by)

        return {
            "query": {
                "bool": {
                    "must": must or [{"match_all": {}}],
                    "filter": filter_clauses,
                }
            },
            "sort": sort,
            "from": (params.page - 1) * params.page_size,
            "size": params.page_size,
            "aggs": self._build_aggregations(),
            "highlight": {
                "fields": {
                    "name": {"number_of_fragments": 0},
                    "description": {"number_of_fragments": 2, "fragment_size": 150},
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
            },
        }

    def _build_sort(self, sort_by: str) -> list:
        sort_options = {
            "relevance": [{"_score": "desc"}],
            "price_asc": [{"price.amount": "asc"}],
            "price_desc": [{"price.amount": "desc"}],
            "newest": [{"created_at": "desc"}],
            "popular": [{"sold_count": "desc"}],
            "rating": [{"rating.average": "desc"}, {"rating.count": "desc"}],
        }
        return sort_options.get(sort_by, sort_options["relevance"])
```

### 9.2 Search API Endpoint

```python
# app/modules/search/api/routes.py

@router.get("/search", response_model=SearchResponse)
async def search_products(
    q: str = Query(default="", max_length=200),
    category: str | None = Query(default=None),
    brands: list[str] | None = Query(default=None),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    in_stock: bool = Query(default=False),
    sort: str = Query(default="relevance"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: SearchService = Depends(get_search_service),
):
    params = SearchParams(
        query=q,
        category_id=category,
        brand_ids=brands,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        in_stock_only=in_stock,
        sort_by=sort,
        page=page,
        page_size=page_size,
    )
    result = await service.search_products(params)

    # Track search query asynchronously
    if q:
        index_search_query.delay(q, result.total)

    return result
```

---

## 10. Performance Optimization

### 10.1 Index Settings

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "5s",
    "max_result_window": 10000,
    "index.search.idle.after": "30s",
    "index.queries.cache.enabled": true
  }
}
```

Phase 2 (scaling):
- `number_of_shards`: 3
- `number_of_replicas`: 1

### 10.2 Query Optimization

| Technique              | Description                                    |
|------------------------|------------------------------------------------|
| **Filter Context**     | Use `filter` for non-scoring clauses (cached)  |
| **Source Filtering**   | Request only needed fields via `_source`       |
| **Request Cache**      | Enable for aggregation-heavy queries           |
| **Shard Request Cache**| Cache aggregation results per shard            |
| **Scroll/Search After**| For deep pagination beyond 10,000 results      |
| **Warm-Up Queries**    | Pre-warm caches for common category searches   |
| **Profile API**        | Identify slow query components                 |

### 10.3 Caching Strategy

```
Search Request
    │
    ├──► Redis Cache Check (query hash key)
    │       │
    │       ├── HIT (TTL: 5 min for listings, 30s for autocomplete)
    │       │   └── Return cached results
    │       │
    │       └── MISS
    │           │
    │           ├──► Elasticsearch Query
    │           │
    │           └──► Cache results in Redis
    │
    └── Invalidation:
        ├── Product update → Invalidate affected query caches
        ├── Price change → Invalidate price-range facet caches
        └── Stock change → Invalidate availability caches
```

---

## 11. Monitoring and Analytics

### 11.1 Search Metrics

| Metric                        | Collection Method               |
|-------------------------------|----------------------------------|
| Search latency (P50/P95/P99) | Prometheus histogram             |
| Queries per second             | Prometheus counter               |
| Zero-result queries            | Application logging              |
| Popular search terms           | Elasticsearch aggregation        |
| Click-through rate             | Frontend event tracking          |
| Conversion from search         | Order attribution                |
| Index size and doc count       | Elasticsearch API                |
| Indexing lag                   | Celery task monitoring           |

### 11.2 Search Quality Metrics

```python
# Tracked for search quality improvement

class SearchAnalytics:
    async def track_search(self, query: str, results_count: int, user_id: str | None):
        """Track every search query for analytics."""
        ...

    async def track_click(self, query: str, product_id: str, position: int):
        """Track when a user clicks a search result."""
        ...

    async def track_add_to_cart(self, query: str, product_id: str):
        """Track when a search leads to add-to-cart."""
        ...

    async def get_zero_result_queries(self, days: int = 7) -> list[str]:
        """Get queries that returned no results."""
        ...

    async def get_trending_queries(self, limit: int = 10) -> list[str]:
        """Get currently trending search queries."""
        ...
```

### 11.3 Alerting Rules

| Alert                           | Condition                         | Severity  |
|---------------------------------|-----------------------------------|-----------|
| Search latency spike            | P95 > 500ms for 5 minutes        | Warning   |
| Search latency critical         | P95 > 1000ms for 2 minutes       | Critical  |
| High zero-result rate           | > 30% of queries return 0 results| Warning   |
| Elasticsearch cluster health    | Status is `red`                   | Critical  |
| Index sync lag                  | > 5 minutes behind               | Warning   |
| Elasticsearch disk usage        | > 85% disk utilized               | Warning   |

---

*For related documentation, see:*
- *[System Architecture](./system.md)*
- *[Backend Architecture](./backend.md)*
- *[Frontend Architecture](./frontend.md)*
- *[Entity Relationship Diagram](./erd.md)*
