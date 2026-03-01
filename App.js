/**
 * App.js — Root Expo application
 * ===============================
 * Handles navigation stack and auth state.
 * 
 * Run: npx expo start
 * Web: npx expo start --web
 * iOS: npx expo start --ios (requires Mac + Xcode)
 * Android: npx expo start --android
 */

import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { StatusBar } from 'expo-status-bar';

// Screens
import LoginScreen      from './src/screens/LoginScreen';
import OnboardingScreen from './src/screens/OnboardingScreen';
import DashboardScreen  from './src/screens/DashboardScreen';
import UploadScreen     from './src/screens/UploadScreen';
import InsightsScreen   from './src/screens/InsightsScreen';
import ReceiptsScreen   from './src/screens/ReceiptsScreen';
import SettingsScreen   from './src/screens/SettingsScreen';
import { AuthContext }  from './src/utils/AuthContext';

const Stack  = createNativeStackNavigator();
const Tab    = createBottomTabNavigator();

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarStyle:       { backgroundColor: '#0d0d1a', borderTopColor: '#1e1e3a' },
        tabBarActiveTintColor:   '#7c3aed',
        tabBarInactiveTintColor: '#6b7280',
        headerShown: false
      }}
    >
      <Tab.Screen name="Home"     component={DashboardScreen}  options={{ tabBarIcon: () => null }} />
      <Tab.Screen name="Upload"   component={UploadScreen}     options={{ tabBarIcon: () => null }} />
      <Tab.Screen name="Receipts" component={ReceiptsScreen}   options={{ tabBarIcon: () => null }} />
      <Tab.Screen name="Insights" component={InsightsScreen}   options={{ tabBarIcon: () => null }} />
      <Tab.Screen name="Settings" component={SettingsScreen}   options={{ tabBarIcon: () => null }} />
    </Tab.Navigator>
  );
}

export default function App() {
  const [authState, setAuthState] = useState({ token: null, loading: true });

  useEffect(() => {
    AsyncStorage.getItem('auth_token').then(token => {
      setAuthState({ token, loading: false });
    });
  }, []);

  if (authState.loading) return null;

  return (
    <AuthContext.Provider value={{ authState, setAuthState }}>
      <NavigationContainer>
        <StatusBar style="light" />
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          {authState.token ? (
            <>
              <Stack.Screen name="Main"       component={MainTabs} />
            </>
          ) : (
            <>
              <Stack.Screen name="Login"      component={LoginScreen} />
              <Stack.Screen name="Onboarding" component={OnboardingScreen} />
            </>
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </AuthContext.Provider>
  );
}
