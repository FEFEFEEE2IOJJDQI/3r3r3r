import { Star, User } from 'lucide-react';
import { useState } from 'react';
import { motion } from 'motion/react';

interface Order {
  id: number;
  timeAgo: string;
  price: number;
  address: string;
  addressLine2: string;
  description: string;
  descriptionLine2: string;
  customer: string;
  rating: number;
}

interface OrderCardProps {
  order: Order;
}

export function OrderCard({ order }: OrderCardProps) {
  const [isClicked, setIsClicked] = useState(false);

  const handleClick = () => {
    setIsClicked(true);
    setTimeout(() => setIsClicked(false), 2000);
  };

  return (
    <div className="bg-[#1a1a1a] rounded-2xl p-4 border border-white/10 shadow-lg hover:border-white/20 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm text-gray-400 font-medium">Заказ #{order.id}</div>
          <div className="text-xs text-gray-500">{order.timeAgo}</div>
        </div>
        <button className="text-xs text-gray-400 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-all font-medium">
          за смену
        </button>
      </div>

      {/* Price */}
      <div className="text-3xl font-bold text-yellow-400 mb-3 tracking-tight">
        {order.price} ₽
      </div>

      {/* Address */}
      <div className="bg-[#0f0f0f] rounded-xl p-3 mb-3 border border-white/5">
        <div className="text-xs text-gray-500 uppercase mb-1 tracking-wider font-semibold">
          Адрес и время
        </div>
        <div className="text-sm font-medium">{order.address}</div>
        <div className="text-sm text-gray-400">{order.addressLine2}</div>
      </div>

      {/* Description */}
      <div className="bg-[#0f0f0f] rounded-xl p-3 mb-3 border border-white/5">
        <div className="text-xs text-gray-500 uppercase mb-1 tracking-wider font-semibold">
          Описание
        </div>
        <div className="text-sm font-medium">{order.description}</div>
        <div className="text-sm text-gray-400">{order.descriptionLine2}</div>
      </div>

      {/* Customer */}
      <div className="bg-[#0f0f0f] rounded-xl p-3 mb-3 border border-white/5">
        <div className="text-xs text-gray-500 uppercase mb-1.5 tracking-wider font-semibold">
          Заказчик
        </div>
        <div className="flex items-center gap-2">
          <div className="text-2xl">
            👤
          </div>
          <div className="flex-1 font-medium">{order.customer}</div>
          <div className="flex items-center gap-1">
            <Star size={14} className="text-yellow-400" fill="currentColor" />
            <span className="text-sm font-semibold">{order.rating.toFixed(1)}</span>
          </div>
        </div>
      </div>

      {/* Action Button */}
      <motion.button
        onClick={handleClick}
        disabled={isClicked}
        className="relative w-full bg-gradient-to-r from-[#f59e42] to-[#f5b042] text-black py-3.5 rounded-xl font-bold overflow-hidden"
        whileTap={{ scale: 0.95 }}
        animate={isClicked ? {
          scale: [1, 1.02, 1],
          transition: { duration: 0.3 }
        } : {}}
      >
        {/* Ripple effect */}
        {isClicked && (
          <>
            <motion.div
              className="absolute inset-0 bg-white rounded-xl"
              initial={{ scale: 0, opacity: 0.8 }}
              animate={{ scale: 2.5, opacity: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
            <motion.div
              className="absolute inset-0 bg-white rounded-xl"
              initial={{ scale: 0, opacity: 0.6 }}
              animate={{ scale: 3, opacity: 0 }}
              transition={{ duration: 0.8, ease: "easeOut", delay: 0.1 }}
            />
          </>
        )}

        {/* Text with animation */}
        <span className="relative z-10 inline-block">
          Откликнуться
        </span>

        {/* Success particles */}
        {isClicked && (
          <div className="absolute inset-0 z-20 pointer-events-none">
            {[...Array(8)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute top-1/2 left-1/2 w-2 h-2 bg-yellow-300 rounded-full"
                initial={{ 
                  scale: 0,
                  x: 0,
                  y: 0,
                  opacity: 1
                }}
                animate={{
                  scale: [0, 1, 0],
                  x: Math.cos((i / 8) * Math.PI * 2) * 60,
                  y: Math.sin((i / 8) * Math.PI * 2) * 60,
                  opacity: [1, 1, 0]
                }}
                transition={{
                  duration: 0.8,
                  ease: "easeOut",
                  delay: 0.1
                }}
              />
            ))}
          </div>
        )}
      </motion.button>
    </div>
  );
}