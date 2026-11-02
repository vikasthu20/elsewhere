import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { Compass, Map, CarFront, CalendarDays, UserRound, Menu, X, Bell } from 'lucide-react';
import { api, token } from '../api';
function storedProfile(){try{return JSON.parse(localStorage.getItem('elsewhere_user')||'null')}catch{return null}}
export function Header(){
 const[open,setOpen]=useState(false);
 const[unread,setUnread]=useState(0);
 const[profile,setProfile]=useState<any>(()=>storedProfile());
 const close=()=>setOpen(false);
 useEffect(()=>{const sync=()=>setProfile(storedProfile());window.addEventListener('storage',sync);window.addEventListener('elsewhere-auth-changed',sync);return()=>{window.removeEventListener('storage',sync);window.removeEventListener('elsewhere-auth-changed',sync)}},[]);
 const displayName=profile?.name||profile?.email||'Your profile';
 const initials=String(profile?.name||profile?.email||'U').trim().split(/[\s@._-]+/).filter(Boolean).slice(0,2).map((part:string)=>part[0]?.toUpperCase()).join('')||'U';
 useEffect(()=>{
  let active=true;
  const refresh=async()=>{if(!token()){if(active)setUnread(0);return}try{const result=await api('/notifications/unread-count');if(active)setUnread(Number(result.unread_count||0))}catch{if(active)setUnread(0)}};
  void refresh();
  const onFocus=()=>void refresh();
  window.addEventListener('focus',onFocus);
  const onVisibility=()=>{if(document.visibilityState==='visible')void refresh()};
  window.addEventListener('visibilitychange',onVisibility);
  const timer=window.setInterval(refresh,10000);
  return()=>{active=false;window.removeEventListener('focus',onFocus);window.removeEventListener('visibilitychange',onVisibility);window.clearInterval(timer)};
 },[]);
 const notificationLink=<span className="header-notification-link"><Bell size={15}/><span>Notifications</span>{unread>0&&<span className="header-notification-badge" aria-label={`${unread} unread notifications`}>{unread>99?'99+':unread}</span>}</span>;
 return <header className="site-header"><Link className="wordmark" to="/" onClick={close}>elsewhere<span>Travel, thoughtfully discovered.</span></Link><nav className="desktop-nav"><NavLink to="/destinations">Destinations</NavLink><NavLink to="/stories">Travel journal</NavLink><NavLink to="/vehicles">Vehicles</NavLink><NavLink to="/planner">Trip planner</NavLink><NavLink to="/trips">Saved trips</NavLink><NavLink to="/notifications">{notificationLink}</NavLink><NavLink to="/about">Our story</NavLink></nav><div className="header-actions">{token()?<Link className="header-profile" to="/account" aria-label={`Open ${displayName} profile`} title={displayName}>{profile?.avatar_url?<img src={profile.avatar_url} alt=""/>:<span>{initials}</span>}</Link>:<><Link className="text-link" to="/login">Log in</Link><Link className="button button-small" to="/register">Get started</Link></>}</div><button className="mobile-menu" aria-label={open?'Close menu':'Open menu'} onClick={()=>setOpen(v=>!v)}>{open?<X/>:<Menu/>}</button>{open&&<nav className="mobile-menu-panel"><Link to="/destinations" onClick={close}>Destinations</Link><Link to="/stories" onClick={close}>Travel journal</Link><Link to="/vehicles" onClick={close}>Vehicles</Link><Link to="/planner" onClick={close}>Trip planner</Link><Link to="/trips" onClick={close}>Saved trips</Link><Link to="/notifications" onClick={close}>{notificationLink}</Link><Link to="/budget" onClick={close}>Budget calculator</Link>{token()?<Link to="/account" onClick={close}>Your profile</Link>:<><Link to="/login" onClick={close}>Log in</Link><Link to="/register" onClick={close}>Create account</Link></>}</nav>}</header>}
export function Footer(){return <footer className="footer"><div><Link className="wordmark" to="/">elsewhere<span>Travel, thoughtfully discovered.</span></Link><p>Made for journeys that stay with you.</p></div><div className="footer-links"><Link to="/destinations">Discover</Link><Link to="/planner">Plan a trip</Link><Link to="/vehicles">Vehicles</Link><Link to="/support">Help & support</Link></div><small>© {new Date().getFullYear()} Elsewhere. Travel thoughtfully.</small></footer>}
export function AppLayout(){return <><Header/><Outlet/><Footer/><nav className="mobile-tabbar"><NavLink to="/"><Compass/>Explore</NavLink><NavLink to="/planner"><Map/>Plan</NavLink><NavLink to="/vehicles"><CarFront/>Rides</NavLink><NavLink to="/budget"><CalendarDays/>Budget</NavLink><NavLink to="/account"><UserRound/>Account</NavLink></nav></>}
