<template>
  <div id="app-layout">
    <header class="app-header">
      <router-link to="/" class="logo">📈 Kronos Stock Predictor</router-link>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #0f1419;
  color: #e7e9ea;
  min-height: 100vh;
}

a {
  color: #1d9bf0;
  text-decoration: none;
}

.app-header {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 24px;
  background: #1a1f26;
  border-bottom: 1px solid #2f3336;
}

.app-header .logo {
  font-size: 20px;
  font-weight: bold;
  color: #e7e9ea;
}

.app-main {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
}
</style>
