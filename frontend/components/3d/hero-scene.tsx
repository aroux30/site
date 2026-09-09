"use client";

import React, { useRef, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, Sparkles, MeshDistortMaterial } from "@react-three/drei";
import * as THREE from "three";

/**
 * 3D Holographic Flagship Gadget
 */
function HolographicDevice({ mousePosition }: { mousePosition: { x: number; y: number } }) {
  const meshRef = useRef<THREE.Group>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const gemRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (!meshRef.current) return;

    // Smooth lerp rotation toward mouse position
    const targetRotX = (mousePosition.y * 0.4) + Math.sin(state.clock.getElapsedTime() * 0.5) * 0.08;
    const targetRotY = (mousePosition.x * 0.6) + state.clock.getElapsedTime() * 0.2;

    meshRef.current.rotation.x = THREE.MathUtils.lerp(meshRef.current.rotation.x, targetRotX, delta * 2.5);
    meshRef.current.rotation.y = THREE.MathUtils.lerp(meshRef.current.rotation.y, targetRotY, delta * 2.5);

    // Orbital ring rotation
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.4;
      ringRef.current.rotation.x += delta * 0.2;
    }

    // Floating gem rotation
    if (gemRef.current) {
      gemRef.current.rotation.y -= delta * 0.8;
      gemRef.current.rotation.x += delta * 0.5;
    }
  });

  return (
    <group ref={meshRef}>
      {/* Central High-Tech Rounded Device Slab */}
      <mesh castShadow receiveShadow position={[0, 0, 0]}>
        <boxGeometry args={[2.2, 3.8, 0.22]} />
        <meshPhysicalMaterial
          color="#064e3b" // Deep emerald
          emissive="#022c22"
          roughness={0.15}
          metalness={0.9}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          reflectivity={0.9}
        />
      </mesh>

      {/* Glossy Front Glass Screen with subtle holographic reflection */}
      <mesh position={[0, 0, 0.12]}>
        <planeGeometry args={[2.05, 3.65]} />
        <meshPhysicalMaterial
          color="#0f172a"
          roughness={0.05}
          metalness={0.2}
          transmission={0.4}
          thickness={0.5}
          ior={1.5}
          clearcoat={1}
        />
      </mesh>

      {/* Screen Glowing Hologram Core */}
      <mesh position={[0, 0.2, 0.13]}>
        <circleGeometry args={[0.7, 32]} />
        <MeshDistortMaterial
          color="#10b981"
          emissive="#047857"
          emissiveIntensity={0.8}
          distort={0.3}
          speed={2}
          roughness={0.2}
        />
      </mesh>

      {/* Camera Module on Back */}
      <group position={[0.55, 1.2, -0.13]}>
        <mesh>
          <boxGeometry args={[0.9, 0.9, 0.1]} />
          <meshStandardMaterial color="#022c22" roughness={0.3} metalness={0.8} />
        </mesh>
        {/* Lenses */}
        <mesh position={[-0.22, 0.22, -0.06]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.15, 0.15, 0.08, 24]} />
          <meshStandardMaterial color="#0f172a" metalness={0.9} roughness={0.1} />
        </mesh>
        <mesh position={[0.22, 0.22, -0.06]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.15, 0.15, 0.08, 24]} />
          <meshStandardMaterial color="#0f172a" metalness={0.9} roughness={0.1} />
        </mesh>
        <mesh position={[-0.22, -0.22, -0.06]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.15, 0.15, 0.08, 24]} />
          <meshStandardMaterial color="#0f172a" metalness={0.9} roughness={0.1} />
        </mesh>
      </group>

      {/* Futuristic Orbiting Gyro Ring */}
      <mesh ref={ringRef} position={[0, 0, 0]}>
        <torusGeometry args={[2.8, 0.04, 16, 100]} />
        <meshStandardMaterial
          color="#34d399"
          emissive="#10b981"
          emissiveIntensity={0.5}
          roughness={0.2}
          metalness={0.9}
        />
      </mesh>

      {/* Satellite Floating Emerald Gem */}
      <Float speed={3} rotationIntensity={2} floatIntensity={2}>
        <mesh ref={gemRef} position={[2.2, -1.2, 0.6]}>
          <octahedronGeometry args={[0.35, 0]} />
          <meshPhysicalMaterial
            color="#10b981"
            emissive="#059669"
            emissiveIntensity={0.6}
            roughness={0.1}
            metalness={0.8}
            transmission={0.3}
          />
        </mesh>
      </Float>

      {/* Secondary Satellite Golden Cube */}
      <Float speed={2.5} rotationIntensity={1.5} floatIntensity={1.5}>
        <mesh position={[-2.1, 1.4, -0.4]}>
          <boxGeometry args={[0.4, 0.4, 0.4]} />
          <meshStandardMaterial
            color="#fbbf24"
            emissive="#d97706"
            emissiveIntensity={0.4}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>
      </Float>
    </group>
  );
}

/**
 * 3D Scene Container
 */
export function Hero3DScene() {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    setMousePosition({ x, y });
  };

  const handleMouseLeave = () => {
    setMousePosition({ x: 0, y: 0 });
  };

  if (!mounted) {
    return (
      <div className="h-[420px] w-full flex items-center justify-center">
        <div className="h-48 w-48 rounded-full bg-primary/20 blur-2xl animate-pulse" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative h-[420px] sm:h-[480px] lg:h-[540px] w-full cursor-grab active:cursor-grabbing select-none"
    >
      <Canvas
        camera={{ position: [0, 0, 7], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[10, 10, 5]} intensity={1.5} color="#ffffff" />
        <pointLight position={[-10, -5, -5]} intensity={1.2} color="#10b981" />
        <pointLight position={[5, -5, 5]} intensity={1.0} color="#34d399" />
        <spotLight
          position={[0, 10, 6]}
          intensity={1.8}
          angle={0.6}
          penumbra={0.8}
          color="#a7f3d0"
        />

        <Float speed={1.8} rotationIntensity={0.6} floatIntensity={0.8}>
          <HolographicDevice mousePosition={mousePosition} />
        </Float>

        {/* Ambient Sparkles */}
        <Sparkles
          count={50}
          scale={7}
          size={2.5}
          speed={0.4}
          opacity={0.6}
          color="#34d399"
        />
      </Canvas>

      {/* Floating 3D Badge Indicator */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-white/15 bg-black/40 px-3.5 py-1 text-[11px] font-semibold text-emerald-300 backdrop-blur-md shadow-lg">
        ✨ نمای سه‌بعدی تعاملی ۳۶۰ درجه (با حرکت ماوس بچرخانید)
      </div>
    </div>
  );
}
