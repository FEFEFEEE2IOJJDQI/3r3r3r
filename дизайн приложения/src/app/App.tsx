import { useState } from "react";
import { Zap, Flame, Star, MoreVertical } from "lucide-react";
import { OrderCard } from "./components/order-card";

export default function App() {
  const [filter, setFilter] = useState<"cheap" | "expensive">(
    "cheap",
  );

  const orders = [
    {
      id: 17,
      timeAgo: "4 ч назад",
      price: 500,
      address: ";!;",
      addressLine2: "13",
      description: "Р-;!;",
      descriptionLine2: "Нужно: 1 чел.",
      customer: "@lalalsIII",
      rating: 0.0,
    },
    {
      id: 16,
      timeAgo: "5 ч назад",
      price: 1200,
      address: "ул. Ленина, 45",
      addressLine2: "кв. 23",
      description: "Доставка продуктов",
      descriptionLine2: "Нужно: 2 чел.",
      customer: "@user123",
      rating: 4.5,
    },
  ];

  return (
    <div className="min-h-screen bg-[#0f0f0f] text-white pb-8">
      {/* Header */}
      <div className="bg-[#1a1a1a] border-b border-white/5 sticky top-0 z-10">
        <div className="flex items-center justify-between px-4 py-3">
          <button className="text-blue-400 font-medium">
            Закрыть
          </button>
          <div className="text-center flex-1">
            <div className="font-semibold">БерузаКаз</div>
            <div className="text-xs text-gray-400">
              мини-приложение
            </div>
          </div>
          <button className="text-blue-400">
            <MoreVertical size={20} />
          </button>
        </div>
      </div>

      <div className="px-4 pt-4 space-y-4">
        {/* Orders Feed Card */}
        <div className="bg-gradient-to-br from-[#2a3a5a] to-[#1a1a2a] rounded-2xl p-4 border border-white/10 shadow-lg">
          {/* Title */}
          <div className="flex items-center gap-2 mb-2">
            <Zap
              className="text-yellow-400"
              size={18}
              fill="currentColor"
            />
            <h2 className="font-semibold text-base">
              Лента заказов
            </h2>
          </div>

          {/* Description */}
          <p className="text-xs text-gray-300 mb-3 leading-relaxed">
            Фильтрация по стоимости и быстрый отклик в один тап
          </p>

          {/* Filter Buttons */}
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => setFilter("cheap")}
              className={`flex-1 py-2.5 rounded-xl transition-all font-semibold text-sm ${
                filter === "cheap"
                  ? "bg-white/20 shadow-md"
                  : "bg-white/5 hover:bg-white/10"
              }`}
            >
              Дешевле
            </button>
            <button
              onClick={() => setFilter("expensive")}
              className={`flex-1 py-2.5 rounded-xl transition-all font-semibold text-sm ${
                filter === "expensive"
                  ? "bg-white/20 shadow-md"
                  : "bg-white/5 hover:bg-white/10"
              }`}
            >
              Дороже
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-black/20 rounded-xl p-3 backdrop-blur-sm">
              <div className="text-xs text-gray-300 mb-0.5 font-medium">
                Всего заявок
              </div>
              <div className="text-2xl font-bold tracking-tight">
                11
              </div>
            </div>
            <div className="bg-black/20 rounded-xl p-3 backdrop-blur-sm">
              <div className="text-xs text-gray-300 mb-0.5 font-medium">
                Средний чек
              </div>
              <div className="text-2xl font-bold tracking-tight">
                3 845 ₽
              </div>
            </div>
          </div>
        </div>

        {/* Active Offers Section */}
        <div className="flex items-center gap-2 px-2 py-2">
          <Flame
            className="text-orange-500"
            size={20}
            fill="currentColor"
          />
          <h3 className="text-gray-300 font-semibold">
            Активные предложения
          </h3>
        </div>

        {/* Order Cards */}
        <div className="space-y-3">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </div>
      </div>
    </div>
  );
}