"use client";

import React, { useState, useEffect, useCallback } from "react";
import { CreditCard, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { DigitalCardDelivery, type DeliveredCard } from "@/components/account/digital-card-delivery";
import apiClient from "@/lib/api/client";

interface OrderSummary {
  id: string;
  order_number: string;
  status: string;
  created_at: string;
}

export default function MyDigitalCodesPage() {
  const { toast } = useToast();
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [cardsByOrder, setCardsByOrder] = useState<Record<string, DeliveredCard[]>>({});
  const [loading, setLoading] = useState(true);

  const fetchDigitalOrders = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch user's delivered orders
      const res = await apiClient.get("/orders/my", { params: { status: "completed" } });
      const orderList: OrderSummary[] = res.data.items || res.data || [];
      setOrders(orderList.slice(0, 20));

      // For each delivered order, fetch its digital cards
      const cardsMap: Record<string, DeliveredCard[]> = {};
      for (const order of orderList.slice(0, 10)) {
        try {
          const cardRes = await apiClient.get(`/inventory/digital/orders/${order.id}/cards`);
          if (Array.isArray(cardRes.data) && cardRes.data.length > 0) {
            cardsMap[order.id] = cardRes.data;
          }
        } catch {
          // No cards for this order
        }
      }
      setCardsByOrder(cardsMap);
    } catch {
      toast({ title: "خطا", description: "بارگذاری کدهای دیجیتال با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDigitalOrders();
  }, [fetchDigitalOrders]);

  const handleCardViewed = (cardId: string) => {
    // Update the reading_at locally
    setCardsByOrder((prev) => {
      const next = { ...prev };
      for (const orderId in next) {
        next[orderId] = next[orderId].map((c) =>
          c.id === cardId && !c.reading_at
            ? { ...c, reading_at: new Date().toISOString() }
            : c
        );
      }
      return next;
    });
  };

  const hasDigitalOrders = Object.keys(cardsByOrder).length > 0;

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" />
            کدهای دیجیتال من
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            پین‌ها، سریال‌ها و فایل‌های لایسنس خریداری‌شده
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchDigitalOrders}>
          <RefreshCw className="h-4 w-4 mr-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !hasDigitalOrders ? (
        <Card className="p-12 text-center">
          <CreditCard className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm text-muted-foreground">
            هنوز هیچ کد دیجیتالی خریداری نکرده‌اید
          </p>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(cardsByOrder).map(([orderId, cards]) => {
            const order = orders.find((o) => o.id === orderId);
            return (
              <div key={orderId} className="space-y-3">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="text-xs" dir="ltr">
                    {order?.order_number || orderId.slice(0, 8)}
                  </Badge>
                  {order?.created_at && (
                    <span className="text-xs text-muted-foreground" dir="ltr">
                      {new Date(order.created_at).toLocaleDateString("fa-IR")}
                    </span>
                  )}
                </div>
                <DigitalCardDelivery
                  orderNumber={order?.order_number || orderId}
                  cards={cards}
                  onCardViewed={handleCardViewed}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
