<template>
  <div class="stick-figures" aria-hidden="true">
    <!-- 跳舞火柴人 -->
    <div class="figure-container" :class="{ paused: reducedMotion }">
      <svg
        class="stick-dancer"
        width="80"
        height="140"
        viewBox="-40 -10 80 140"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <!-- 头 -->
        <circle cx="0" cy="-5" r="12" class="head" />
        <!-- 身体 -->
        <line x1="0" y1="7" x2="0" y2="55" class="body" />
        <!-- 左臂 -->
        <line x1="0" y1="18" x2="-22" y2="40" class="arm-left" />
        <!-- 右臂 -->
        <line x1="0" y1="18" x2="22" y2="5" class="arm-right" />
        <!-- 左腿 -->
        <line x1="0" y1="55" x2="-18" y2="100" class="leg-left" />
        <!-- 右腿 -->
        <line x1="0" y1="55" x2="20" y2="100" class="leg-right" />
      </svg>
    </div>

    <!-- 走路小恐龙 -->
    <div class="figure-container dino-container" :class="{ paused: reducedMotion }">
      <svg
        class="stick-dino"
        width="120"
        height="100"
        viewBox="0 0 120 100"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <!-- 身体 -->
        <ellipse cx="55" cy="55" rx="28" ry="18" class="dino-body" />
        <!-- 头 -->
        <ellipse cx="90" cy="38" rx="16" ry="14" class="dino-head" />
        <!-- 眼睛 -->
        <circle cx="96" cy="35" r="3" fill="currentColor" stroke="none" />
        <!-- 嘴 -->
        <line x1="100" y1="42" x2="106" y2="41" />
        <!-- 尾巴 -->
        <path d="M27 55 Q10 40 15 25" class="dino-tail" />
        <!-- 前腿 -->
        <line x1="70" y1="72" x2="78" y2="92" class="dino-front-leg" />
        <line x1="78" y1="92" x2="86" y2="92" class="dino-front-foot" />
        <!-- 后腿 -->
        <line x1="42" y1="72" x2="32" y2="92" class="dino-back-leg" />
        <line x1="32" y1="92" x2="24" y2="92" class="dino-back-foot" />
        <!-- 地面 -->
        <line x1="5" y1="94" x2="115" y2="94" stroke-width="2" stroke-dasharray="6 4" opacity="0.3" />
      </svg>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const reducedMotion = ref(false)

let mq = null

onMounted(() => {
  mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = mq.matches
  mq.addEventListener('change', onReducedMotionChange)
})

onBeforeUnmount(() => {
  if (mq) mq.removeEventListener('change', onReducedMotionChange)
})

function onReducedMotionChange(e) {
  reducedMotion.value = e.matches
}
</script>

<style scoped>
.stick-figures {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 80px;
  padding: 60px 20px 20px;
  color: var(--text-primary);
}

.figure-container {
  transition: all var(--duration-normal) var(--ease-out);
}

.figure-container.paused svg * {
  animation: none !important;
}

/* ===== 跳舞火柴人 ===== */
.stick-dancer .head {
  animation: headBob 0.6s ease-in-out infinite alternate;
  transform-origin: 0 0;
}

.stick-dancer .arm-left {
  animation: armLeftSwing 0.5s ease-in-out infinite alternate;
  transform-origin: 0 18px;
}

.stick-dancer .arm-right {
  animation: armRightSwing 0.5s ease-in-out 0.1s infinite alternate;
  transform-origin: 0 18px;
}

.stick-dancer .leg-left {
  animation: legLeftKick 0.5s ease-in-out infinite alternate;
  transform-origin: 0 55px;
}

.stick-dancer .leg-right {
  animation: legRightKick 0.5s ease-in-out 0.1s infinite alternate;
  transform-origin: 0 55px;
}

.stick-dancer .body {
  animation: bodyTilt 0.5s ease-in-out infinite alternate;
  transform-origin: 0 7px;
}

@keyframes headBob {
  0% { transform: translateY(0); }
  100% { transform: translateY(-3px); }
}

@keyframes armLeftSwing {
  0% { transform: rotate(-25deg); }
  100% { transform: rotate(30deg); }
}

@keyframes armRightSwing {
  0% { transform: rotate(15deg); }
  100% { transform: rotate(-35deg); }
}

@keyframes legLeftKick {
  0% { transform: rotate(-20deg); }
  100% { transform: rotate(25deg); }
}

@keyframes legRightKick {
  0% { transform: rotate(15deg); }
  100% { transform: rotate(-30deg); }
}

@keyframes bodyTilt {
  0% { transform: rotate(-2deg); }
  100% { transform: rotate(2deg); }
}

/* ===== 走路小恐龙 ===== */
.dino-container {
  animation: dinoWalk 3s ease-in-out infinite;
}

@keyframes dinoWalk {
  0% { transform: translateX(20px); }
  50% { transform: translateX(-10px); }
  100% { transform: translateX(20px); }
}

.stick-dino .dino-tail {
  animation: tailWag 0.8s ease-in-out infinite alternate;
  transform-origin: 27px 55px;
}

.stick-dino .dino-front-leg {
  animation: dinoFrontLeg 0.5s ease-in-out infinite alternate;
  transform-origin: 70px 72px;
}

.stick-dino .dino-back-leg {
  animation: dinoBackLeg 0.5s ease-in-out 0.25s infinite alternate;
  transform-origin: 42px 72px;
}

@keyframes tailWag {
  0% { transform: rotate(-10deg); }
  100% { transform: rotate(15deg); }
}

@keyframes dinoFrontLeg {
  0% { transform: rotate(-15deg); }
  100% { transform: rotate(15deg); }
}

@keyframes dinoBackLeg {
  0% { transform: rotate(15deg); }
  100% { transform: rotate(-15deg); }
}

/* ===== 响应式 ===== */
@media (max-width: 639px) {
  .stick-figures {
    gap: 30px;
    padding: 40px 10px 10px;
  }
  .stick-dancer {
    width: 60px;
    height: 110px;
  }
  .stick-dino {
    width: 90px;
    height: 80px;
  }
}

@media (max-width: 374px) {
  .stick-figures {
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }
}
</style>
