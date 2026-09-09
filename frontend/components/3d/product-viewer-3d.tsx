"use client";

import React, { useRef, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stage, Float, Sparkles, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { RotateCw, ZoomIn, Palette, Eye, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export type ColorFinish = "emerald" | "titanium" | "gold" | "silver";

interface FinishConfig {
  name: string;
  bodyColor: string;
  emissiveColor: string;
  metalness: number;
  roughness: number;
}

const FINISH_CONFIGS: Record<ColorFinish, FinishConfig> = {
  emerald: {
    name: "سبز زمردی",
    bodyColor: "#064e3b",
    emissiveColor: "#022c22",
    metalness: 0.9,
    roughness: 0.15,
  },
  titanium: {
    name: "تیتانیوم مشکی",
    bodyColor: "#1e293b",
    emissiveColor: "#0f172a",
    metalness: 0.95,
    roughness: 0.2,
  },
  gold: {
    name: "طلایی کهربایی",
    bodyColor: "#d97706",
    emissiveColor: "#78350f",
    metalness: 0.9,
    roughness: 0.18,
  },
  silver: {
    name: "نقره‌ای مات",
    bodyColor: "#94a3b8",
    emissiveColor: "#334155",
    metalness: 0.85,
    roughness: 0.25,
  },
};

function Product3DModel({
  finish,
  wireframe,
}: {
  finish: ColorFinish;
  wireframe: boolean;
}) {
  const cfg = FINISH_CONFIGS[finish];

  return (
    <group>
      {/* Main Flagship Body */}
      <mesh castShadow receiveShadow position={[0, 0, 0]}>
        <boxGeometry args={[2.4, 4.2, 0.28]} />
        <meshPhysicalMaterial
          color={cfg.bodyColor}
          emissive={cfg.emissiveColor}
          roughness={cfg.roughness}
          metalness={cfg.metalness}
          clearcoat={1}
          clearcoatRoughness={0.1}
          wireframe={wireframe}
        />
      </mesh>

      {/* Front Glass Screen */}
      <mesh position={[0, 0, 0.15]}>
        <planeGeometry args={[2.25, 4.05]} />
        <meshPhysicalMaterial
          color="#020617"
          roughness={0.05}
          metalness={0.1}
          transmission={0.3}
          ior={1.52}
          clearcoat={1}
          wireframe={wireframe}
        />
      </mesh>

      {/* Camera Housing Plateau */}
      <group position={[0.6, 1.3, -0.16]}>
        <mesh castShadow>
          <boxGeometry args={[1.0, 1.1, 0.14]} />
          <meshStandardMaterial
            color="#020617"
            metalness={0.9}
            roughness={0.2}
            wireframe={wireframe}
          />
        </mesh>
        {/* Lenses */}
        {[-0.26, 0.26].map((x, i) => (
          <mesh key={i} position={[x, 0.26, -0.08]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.18, 0.18, 0.1, 32]} />
            <meshStandardMaterial color="#09090b" metalness={0.95} roughness={0.05} />
          </mesh>
        ))}
        <mesh position={[0, -0.26, -0.08]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.22, 0.22, 0.1, 32]} />
          <meshStandardMaterial color="#09090b" metalness={0.95} roughness={0.05} />
        </mesh>
      </group>

      {/* Edge Titanium Chamfer Trim */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[2.42, 4.22, 0.04]} />
        <meshStandardMaterial
          color="#10b981"
          emissive="#059669"
          emissiveIntensity={0.2}
          metalness={1}
          roughness={0.1}
          wireframe={wireframe}
        />
      </mesh>
    </group>
  );
}

interface Product3DViewerProps {
  title?: string;
  initialFinish?: ColorFinish;
}

export function Product3DViewer({
  title = "مشاهده مدل سه‌بعدی کالا",
  initialFinish = "emerald",
}: Product3DViewerProps) {
  const [finish, setFinish] = useState<ColorFinish>(initialFinish);
  const [wireframe, setWireframe] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="h-[460px] w-full rounded-3xl border border-border bg-card/60 flex items-center justify-center">
        <div className="h-16 w-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="relative h-[460px] sm:h-[500px] w-full rounded-3xl border border-border bg-gradient-to-b from-card via-background to-muted/30 p-4 shadow-sm overflow-hidden flex flex-col justify-between">
      {/* Top Controls Bar */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
        <div className="flex items-center gap-2">
          <Badge className="bg-primary/10 text-primary border-primary/20 text-xs px-2.5 py-1 gap-1">
            <RotateCw className="h-3 w-3 animate-spin" style={{ animationDuration: "6s" }} />
            <span>۳۶۰ درجه Real-time</span>
          </Badge>
          <span className="text-xs font-bold text-foreground hidden sm:inline">
            {title}
          </span>
        </div>

        {/* Color Switcher & Options */}
        <div className="flex items-center gap-2">
          {/* Finish selector */}
          <div className="flex items-center gap-1.5 rounded-xl border border-border bg-background/80 p-1 backdrop-blur-md">
            {(Object.keys(FINISH_CONFIGS) as ColorFinish[]).map((f) => {
              const cfg = FINISH_CONFIGS[f];
              const isSelected = finish === f;
              return (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFinish(f)}
                  title={cfg.name}
                  className={`h-6 w-6 rounded-lg transition-transform ${
                    isSelected ? "scale-110 ring-2 ring-primary ring-offset-1" : "opacity-70 hover:opacity-100"
                  }`}
                  style={{ backgroundColor: cfg.bodyColor }}
                />
              );
            })}
          </div>

          {/* Wireframe Toggle */}
          <Button
            size="sm"
            variant={wireframe ? "default" : "outline"}
            onClick={() => setWireframe(!wireframe)}
            className="h-8 rounded-xl px-2.5 text-xs gap-1"
          >
            <Eye className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">ساختار (Wireframe)</span>
          </Button>

          {/* Auto-rotate Toggle */}
          <Button
            size="sm"
            variant={autoRotate ? "default" : "outline"}
            onClick={() => setAutoRotate(!autoRotate)}
            className="h-8 rounded-xl px-2.5 text-xs gap-1"
          >
            <RotateCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">چرخش خودکار</span>
          </Button>
        </div>
      </div>

      {/* 3D Canvas */}
      <div className="relative h-full w-full cursor-grab active:cursor-grabbing touch-none select-none">
        <Canvas
          camera={{ position: [0, 0, 6.5], fov: 45 }}
          gl={{ antialias: true, alpha: true }}
          dpr={[1, 2]}
        >
          <ambientLight intensity={0.8} />
          <directionalLight position={[10, 10, 5]} intensity={1.5} />
          <directionalLight position={[-10, 5, -5]} intensity={1.0} color="#10b981" />
          <pointLight position={[0, -5, 5]} intensity={0.6} color="#38bdf8" />

          <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.5}>
            <Product3DModel finish={finish} wireframe={wireframe} />
          </Float>

          <ContactShadows
            position={[0, -2.4, 0]}
            opacity={0.6}
            scale={8}
            blur={1.8}
            far={4}
          />

          <OrbitControls
            enableZoom={true}
            enablePan={false}
            autoRotate={autoRotate}
            autoRotateSpeed={1.8}
            minDistance={4}
            maxDistance={10}
          />

          <Sparkles count={25} scale={6} size={2} color="#10b981" opacity={0.4} />
        </Canvas>
      </div>

      {/* Bottom Hint */}
      <div className="relative z-10 flex items-center justify-between border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
        <span>رنگ بدنه: <strong className="text-foreground">{FINISH_CONFIGS[finish].name}</strong></span>
        <span>برای چرخش بکشید • اسکرول برای بزرگ‌نمایی</span>
      </div>
    </div>
  );
}
