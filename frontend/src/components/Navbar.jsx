import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  if (!user) return null;

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to={user.role === 'seller' ? '/seller' : '/buyer'} className="navbar-brand">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <span>AuctionHub</span>
        </Link>

        <div className="navbar-links">
          {user.role === 'buyer' && (
            <>
              <Link to="/buyer" className="nav-link">Dashboard</Link>
              <Link to="/buyer/my-bids" className="nav-link">My Bids</Link>
            </>
          )}
          {user.role === 'seller' && (
            <>
              <Link to="/seller" className="nav-link">Dashboard</Link>
              <Link to="/seller/create" className="nav-link">Create Auction</Link>
            </>
          )}
          <Link to="/demo" className="nav-link">DC Demo</Link>
        </div>

        <div className="navbar-user">
          <div className="user-badge">
            <span className={`role-dot ${user.role}`}></span>
            <span className="username">{user.username}</span>
            <span className="role-label">{user.role}</span>
          </div>
          <button onClick={handleLogout} className="btn btn-ghost btn-sm">
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
