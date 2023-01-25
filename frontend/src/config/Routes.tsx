import React, { FC, useState, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Dashboard from "../components/Dashboard/Dashboard";
import ViewPlans from "../pages/ViewPlans";
import ViewCustomers from "../pages/ViewCustomers";
import SettingsPage from "../pages/SettingsPage";
import StripeRedirect from "../integrations/PaymentProcessorIntegrations";
import SideBar from "../components/SideBar";
import { Layout } from "antd";
import CreatePlan from "../pages/CreatePlan";
import ViewMetrics from "../pages/ViewMetrics";
import ViewExperiments from "../pages/ViewExperiments";
import CreateBacktest from "../pages/CreateBacktest";
import ExperimentResults from "../pages/ExperimentResults";
import PlanDetails from "../components/Plans/PlanDetails/PlanDetails";
import EditPlanLoader from "../pages/EditPlanLoader";
import StripeIntegrationView from "../integrations/pages/StripeIntegrationView";
import CreateCredit from "../pages/CreateBalanceAdjustment";
import ViewAddOns from "../pages/ViewAddOns";
import CreateAddOns from "../pages/CreateAddOns";
import AddonDetails from "../components/Addons/AddonsDetails/AddonDetails";

const { Sider } = Layout;

const getSettingsTab = (component) => {
  // @ts-ignore
  // return import.meta.env.VITE_IS_DEMO ? <Navigate replace to={"/"} /> :component
  return component;
};

const AppRoutes: FC = () => {
  const [collapse, setCollapse] = useState(false);
  const { pathname } = useLocation();
  const handleToggle = (event: any) => {
    event.preventDefault();
    collapse ? setCollapse(false) : setCollapse(true);
  };
  const currentPath = pathname.split("/")[1];
  useEffect(() => {
    window.innerWidth <= 760 ? setCollapse(true) : setCollapse(false);
  }, []);
  return (
    <div className="bg-darkgold">
      <Layout>
        <Sider
          trigger={null}
          collapsible={false}
          collapsed={collapse}
          style={{ minHeight: "100vh", background: "#FAFAFA" }}
        >
          <SideBar />
        </Sider>

        <Layout
          style={
            currentPath === "plans" || currentPath === "add-ons"
              ? { background: "#ffffff" }
              : { background: "#FAFAFA" }
          }
        >
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/" element={<Dashboard />} />
            <Route path="/plans" element={<ViewPlans />} />
            <Route path="/plans/:planId" element={<PlanDetails />} />
            <Route path="create-plan" element={<CreatePlan />} />
            <Route path="create-addons" element={<CreateAddOns />} />
            <Route path="/add-ons" element={<ViewAddOns />} />
            <Route path="/add-ons/:addOnId" element={<AddonDetails />} />
            <Route
              path="create-version/:planId"
              element={<EditPlanLoader type="version" />}
            />
            <Route
              path="create-custom/:planId"
              element={<EditPlanLoader type="custom" />}
            />{" "}
            <Route
              path="backtest-plan/:planId"
              element={<EditPlanLoader type="backtest" />}
            />
            <Route path="/plan" />
            <Route path="/customers" element={<ViewCustomers />} />
            <Route path="/metrics" element={<ViewMetrics />} />
            <Route path="/customers-create" element={<CreatePlan />} />
            {/* <Route
              path="/customers-create-credit/:customerId"
              element={<CreateCredit />}
            /> */}
            <Route
              path="/settings/:tab"
              element={getSettingsTab(<SettingsPage />)}
            />
            <Route
              path="settings/integrations/stripe"
              element={getSettingsTab(<StripeIntegrationView />)}
            />
            <Route path="/redirectstripe" element={<StripeRedirect />} />
            <Route path="/experiments" element={<ViewExperiments />} />
            <Route path="/experiment">
              <Route path=":experimentId" element={<ExperimentResults />} />
            </Route>
            <Route path="create-experiment" element={<CreateBacktest />} />
            {/* <Route path="/experiment">
              <Route path=":experimentId" element={<ExperimentPage />} />
            </Route> */}
            <Route path="*" element={<Navigate to="/dashboard" />} />
          </Routes>
        </Layout>
      </Layout>
    </div>
  );
};

export default AppRoutes;
