import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import { CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";
import LoadingSpinner from "../components/LoadingSpinner";

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  useEffect(() => {
    Customer.getCustomers().then((data) => {
      setCustomers(data);
    });
  }, []);

  if (customers.length === 0) {
    return (
      <div>
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div>
      <CustomerTable customerArray={customers} />
    </div>
  );
};

export default ViewCustomers;
