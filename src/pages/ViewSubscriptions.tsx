import React, { FC, useEffect, useState } from "react";
import { CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";

const ViewSubscriptions: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  return <div></div>;
};

export default ViewSubscriptions;
